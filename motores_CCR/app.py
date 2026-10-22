"""Interfaz común para los motores actuariales de CCR."""

import base64
import os
import shutil
import subprocess
import sys
from datetime import date, datetime
from typing import TypedDict
from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent


class MotorDefinition(TypedDict):
    label: str
    directory: Path
    reserve: str
    script: str
    config_files: tuple[str, ...]
    parameter_names: tuple[str, ...] | None


MOTORS: dict[str, MotorDefinition] = {
    "ley100": {
        "label": "Ley 100",
        "directory": BASE_DIR / "motores" / "ley100",
        "reserve": "Ley100",
        "script": "motor_ley100.py",
        "config_files": ("config_cierre.txt", "config.txt"),
        "parameter_names": None,
    },
    "arl": {
        "label": "ARL",
        "directory": BASE_DIR / "motores" / "arl",
        "reserve": "RM",
        "script": "motor_arl.py",
        "config_files": ("config_cierre.txt",),
        "parameter_names": None,
    },
}

DATE_PARAMETERS = {"Fecha valoración t-1", "Fecha valoración t", "Fecha Cierre"}
NUMERIC_PARAMETERS = {"SMMLV", "Inflacion"}
BOOLEAN_VALUES = ("True", "False")
HEADER_BLUE = "#0B4F9E"


def selected_motor() -> tuple[str, MotorDefinition]:
    requested = st.query_params.get("motor", "ley100").lower()
    if requested not in MOTORS:
        st.warning("Ese motor aún no está disponible. Se seleccionó Ley 100.")
        requested = "ley100"

    labels = {motor["label"]: key for key, motor in MOTORS.items()}
    selector, _ = st.columns([1.5, 4.5])
    with selector:
        selected_label = st.selectbox(
            "Seleccionar motor",
            list(labels),
            index=list(labels).index(MOTORS[requested]["label"]),
        )
    key = labels[selected_label]
    st.query_params["motor"] = key
    return key, MOTORS[key]


def read_config(engine_dir: Path) -> pd.DataFrame:
    return pd.read_csv(
        engine_dir / "config_cierre.txt",
        sep=";",
        dtype=str,
        keep_default_na=False,
    )


def save_config(
    engine_dir: Path,
    original: pd.DataFrame,
    edited: pd.DataFrame,
    config_files: tuple[str, ...],
) -> None:
    values = dict(zip(edited["Parametro"], edited["Valor"]))
    updated = original.copy()
    mask = updated["Parametro"].isin(values)
    updated.loc[mask, "Valor"] = updated.loc[mask, "Parametro"].map(values)
    for name in config_files:
        updated.to_csv(
            engine_dir / name,
            sep=";",
            index=False,
            encoding="utf-8",
            lineterminator="\n",
        )


def month_folder(config: pd.DataFrame) -> str:
    values = dict(zip(config["Parametro"], config["Valor"]))
    year, month, *_ = values["Fecha Cierre"].split("/")
    return f"{year}{month}"


def clear_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for item in path.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def file_count(path: Path) -> int:
    return sum(1 for item in path.rglob("*") if item.is_file()) if path.exists() else 0


def prepare_period_folder(engine_dir: Path, folder: str) -> list[str]:
    """Deja inputs/{folder} listo: parametros del mes anterior, salida y t_consolidada vacías."""
    inputs_dir = engine_dir / "inputs"
    target = inputs_dir / folder
    existed = target.exists()
    messages = [
        f"La carpeta inputs/{folder} existe."
        if existed
        else f"La carpeta inputs/{folder} no existe, procedo a crearla."
    ]

    previous = sorted(
        path
        for path in inputs_dir.iterdir()
        if path.is_dir() and path.name.isdigit() and path.name < folder
        and (path / "parametros").is_dir()
    ) if inputs_dir.exists() else []
    if previous:
        source = previous[-1]
        if (target / "parametros").exists():
            shutil.rmtree(target / "parametros")
        shutil.copytree(source / "parametros", target / "parametros")
        messages.append(f"parametros copiada de inputs/{source.name}.")
    else:
        (target / "parametros").mkdir(parents=True, exist_ok=True)
        messages.append(
            "No hay un periodo anterior para copiar; cargue los archivos de parametros."
        )

    clear_folder(target / "salida")
    clear_folder(target / "t_consolidada")
    messages.append("salida y t_consolidada quedaron vacías.")
    return messages


def ensure_previous_consolidated(engine_dir: Path, config: pd.DataFrame) -> None:
    """El motor ARL guarda 'nuevas nuevas' en t_consolidada del mes anterior."""
    values = dict(zip(config["Parametro"], config["Valor"]))
    previous_month = values.get("Fecha valoración t-1", "")
    if len(previous_month) >= 7:
        previous_folder = previous_month[:4] + previous_month[5:7]
        (engine_dir / "inputs" / previous_folder / "t_consolidada").mkdir(
            parents=True, exist_ok=True
        )


def required_inputs(
    engine_dir: Path,
    folder: str,
    motor_key: str,
    motor: MotorDefinition,
    config: pd.DataFrame,
) -> dict[str, Path]:
    root = engine_dir / "inputs" / folder
    reserve = motor["reserve"]
    targets = {
        **{
            name: root / "t_consolidada"
            for name in consolidated_input_names(folder, reserve)
        },
        "hip_deslizamiento.csv": root / "parametros",
        "rx_cambio_grupo.csv": root / "parametros",
    }
    if motor_key == "arl":
        targets.update(
            {
                "utils.xlsx": engine_dir,
                "Consolidado tasas equivalentes RM.xlsx": root / "parametros",
                "vector_tmr.csv": root / "parametros",
            }
        )
        values = dict(zip(config["Parametro"], config["Valor"]))
        year = values["Fecha Cierre"].split("/")[0]
        mortality_table = (
            engine_dir
            / "tablas_mort_edad"
            / reserve
            / year
            / "tabla_mort_0.csv"
        )
        if not mortality_table.exists():
            targets["factores_mejora.xlsx"] = root / "parametros"
            targets["tablas_mortalidad.csv"] = root / "parametros"
        if values.get("bd_t_1", "False").strip().lower() == "true":
            previous_month = values["Fecha valoración t-1"]
            previous_folder = previous_month[:4] + previous_month[5:7]
            targets[f"{previous_folder}_{reserve}.xlsx"] = (
                engine_dir
                / "inputs"
                / previous_folder
                / "salida"
                / reserve
            )
    return targets


def consolidated_input_names(folder: str, reserve: str) -> tuple[str, str]:
    return (
        f"{folder}_t_consolidada_Nuevo_{reserve}.csv",
        f"{folder}_t_consolidada_Stock_{reserve}.csv",
    )


def store_uploaded_file(directory: Path, name: str, contents: bytes) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / name
    destination.write_bytes(contents)
    return destination


def period_area_path(engine_dir: Path, folder: str, area: str) -> Path:
    if area not in {"parametros", "salida", "t_consolidada"}:
        raise ValueError(f"Carpeta de periodo no permitida: {area}")
    return engine_dir / "inputs" / folder / area


def resolve_period_file(
    engine_dir: Path,
    folder: str,
    area: str,
    relative_name: str,
) -> Path:
    area_dir = period_area_path(engine_dir, folder, area).resolve()
    target = (area_dir / relative_name).resolve()
    try:
        target.relative_to(area_dir)
    except ValueError as error:
        raise ValueError("La ruta del archivo está fuera de la carpeta seleccionada.") from error
    if not target.is_file():
        raise FileNotFoundError(f"No se encontró el archivo: {relative_name}")
    return target


def is_running(key: str) -> bool:
    process = st.session_state.get("processes", {}).get(key)
    return process is not None and process.poll() is None


def start_run(
    key: str,
    engine_dir: Path,
    script: str,
    password: str | None = None,
) -> None:
    if key == "arl" and not password:
        st.error("Ingrese la contraseña de ARL para iniciar el cálculo.")
        return

    if key == "arl":
        ensure_previous_consolidated(engine_dir, read_config(engine_dir))

    log_dir = engine_dir / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "ultima_ejecucion.log"
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
    }
    if password is not None:
        env["MOTOR_ARL_PASSWORD"] = password
    with log_file.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, str(engine_dir / script)],
            cwd=engine_dir,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
        )
    st.session_state.setdefault("processes", {})[key] = process
    st.session_state.setdefault("refresh_results_after_run", {})[key] = True


@st.fragment(run_every=3)
def run_status(key: str, engine_dir: Path) -> None:
    process = st.session_state.get("processes", {}).get(key)
    if process is None:
        st.info("Aún no se ha ejecutado el motor en esta sesión.")
        return

    code = process.poll()
    if code is None:
        st.warning("El cálculo está en ejecución. Puede tardar varios minutos.")
    elif code == 0:
        st.success("El cálculo terminó correctamente.")
    else:
        st.error(f"El cálculo terminó con error (código {code}). Revise el log.")

    refresh_pending = st.session_state.setdefault("refresh_results_after_run", {})
    if code is not None and refresh_pending.get(key, False):
        refresh_pending[key] = False
        st.rerun(scope="app")

    log_file = engine_dir / "logs" / "ultima_ejecucion.log"
    if log_file.exists():
        st.code(
            log_file.read_text(encoding="utf-8", errors="replace")[-6000:]
            or "(sin salida todavía)"
        )


st.set_page_config(page_title="Motores CCR", layout="wide")
logo = base64.b64encode((BASE_DIR.parent / "LogoSura_sinFondo.png").read_bytes()).decode("ascii")
st.markdown(
    f"""
    <div style="text-align:center;">
        <img src="data:image/png;base64,{logo}" alt="Logo SURA"
             style="width:112px;max-width:100%;height:auto;">
        <h1 style="text-align:center;margin-top:.25rem;">Motores actuariales CCR</h1>
    </div>
    """,
    unsafe_allow_html=True,
)
motor_key, motor = selected_motor()
engine_dir = Path(motor["directory"])
st.caption(f"Motor seleccionado: {motor['label']}")

config = read_config(engine_dir)
running = is_running(motor_key)
pending_setup = st.session_state.get("period_setup_pending")
is_confirming_period = (
    pending_setup is not None and pending_setup["motor_key"] == motor_key
)

st.subheader("1. Parámetros")
st.markdown(
    f"""
    <style>
    .param-header {{background:{HEADER_BLUE};color:#fff;font-weight:600;
        padding:.45rem .75rem;border-radius:4px;}}
    </style>
    """,
    unsafe_allow_html=True,
)
header_name, header_value = st.columns([1, 2])
header_name.markdown('<div class="param-header">Parametro</div>', unsafe_allow_html=True)
header_value.markdown('<div class="param-header">Valor</div>', unsafe_allow_html=True)

saved_values = dict(zip(config["Parametro"], config["Valor"]))
current_values: dict[str, str] = {}
invalid_parameters: list[str] = []
for name, saved in saved_values.items():
    name_column, value_column = st.columns([1, 2], vertical_alignment="center")
    name_column.write(name)
    widget_key = f"param_{motor_key}_{name}"
    with value_column:
        if name in DATE_PARAMETERS:
            try:
                default_date = datetime.strptime(saved, "%Y/%m/%d").date()
            except ValueError:
                default_date = date.today()
            chosen = st.date_input(
                name,
                value=default_date,
                format="YYYY/MM/DD",
                key=widget_key,
                label_visibility="collapsed",
                disabled=is_confirming_period,
            )
            current_values[name] = chosen.strftime("%Y/%m/%d")
        elif saved in BOOLEAN_VALUES:
            current_values[name] = st.selectbox(
                name,
                BOOLEAN_VALUES,
                index=BOOLEAN_VALUES.index(saved),
                key=widget_key,
                label_visibility="collapsed",
                disabled=is_confirming_period,
            )
        else:
            text = st.text_input(
                name,
                value=saved,
                key=widget_key,
                label_visibility="collapsed",
                disabled=is_confirming_period,
            ).strip()
            if name in NUMERIC_PARAMETERS:
                try:
                    float(text)
                except ValueError:
                    invalid_parameters.append(name)
                    st.error("Ingrese un número válido.")
            elif not text:
                invalid_parameters.append(name)
                st.error("Este parámetro no puede estar vacío.")
            current_values[name] = text

smmlv_changed = current_values.get("SMMLV") != saved_values.get("SMMLV")
smmlv_confirmed = True
if smmlv_changed:
    st.warning("Recuerda que este parámetro (SMMLV) se cambia cada año. ¿Está seguro?")
    smmlv_confirmed = st.checkbox(
        "Sí, estoy seguro de cambiar el SMMLV",
        key=f"smmlv_confirm_{motor_key}",
        disabled=is_confirming_period,
    )

edited = pd.DataFrame(
    {"Parametro": list(current_values), "Valor": list(current_values.values())}
)
effective_config = config.copy()
edited_values = dict(zip(edited["Parametro"], edited["Valor"]))
config_mask = effective_config["Parametro"].isin(edited_values)
effective_config.loc[config_mask, "Valor"] = (
    effective_config.loc[config_mask, "Parametro"].map(edited_values)
)
folder = month_folder(effective_config)

if st.button(
    "Guardar parámetros",
    disabled=running
    or is_confirming_period
    or bool(invalid_parameters)
    or not smmlv_confirmed,
):
    if (engine_dir / "inputs" / folder).exists():
        st.session_state["period_setup_pending"] = {
            "motor_key": motor_key,
            "folder": folder,
            "stage": "ask",
        }
    else:
        save_config(engine_dir, config, edited, motor["config_files"])
        st.session_state["period_messages"] = [
            "Parámetros guardados.",
            *prepare_period_folder(engine_dir, folder),
        ]
    st.rerun()

if is_confirming_period:
    pending_folder = pending_setup["folder"]
    period_dir = engine_dir / "inputs" / pending_folder
    st.warning(
        f"La carpeta inputs/{pending_folder} ya existe. Contiene "
        f"{file_count(period_dir / 'parametros')} archivo(s) en parametros, "
        f"{file_count(period_dir / 'salida')} en salida y "
        f"{file_count(period_dir / 't_consolidada')} en t_consolidada."
    )
    if pending_setup["stage"] == "ask":
        st.write("¿Desea volver a preparar esta carpeta para calcular ese cierre?")
        yes_column, no_column = st.columns(2)
        if yes_column.button("Sí, continuar", key=f"period_yes_{motor_key}_{pending_folder}"):
            pending_setup["stage"] = "confirm"
            st.session_state["period_setup_pending"] = pending_setup
            st.rerun()
        if no_column.button("No", key=f"period_no_{motor_key}_{pending_folder}"):
            st.session_state.pop("period_setup_pending", None)
            st.session_state["period_messages"] = [
                "Revise la Fecha de Cierre. No se guardaron los parámetros ni se modificaron archivos."
            ]
            st.rerun()
    else:
        st.error(
            "Al confirmar, se guardarán los parámetros, se reemplazará la carpeta "
            "parametros con la del periodo anterior más reciente y se vaciarán "
            "salida y t_consolidada."
        )
        confirm_column, cancel_column = st.columns(2)
        if confirm_column.button(
            "Confirmar y preparar",
            type="primary",
            key=f"period_confirm_{motor_key}_{pending_folder}",
        ):
            save_config(engine_dir, config, edited, motor["config_files"])
            st.session_state["period_messages"] = [
                "Parámetros guardados.",
                *prepare_period_folder(engine_dir, pending_folder),
            ]
            st.session_state.pop("period_setup_pending", None)
            st.rerun()
        if cancel_column.button(
            "Cancelar",
            key=f"period_cancel_{motor_key}_{pending_folder}",
        ):
            st.session_state.pop("period_setup_pending", None)
            st.session_state["period_messages"] = [
                "Revise la Fecha de Cierre. No se guardaron los parámetros ni se modificaron archivos."
            ]
            st.rerun()

for line in st.session_state.pop("period_messages", []):
    st.info(line)
st.caption(f"Carpeta de trabajo según Fecha Cierre: inputs/{folder}.")
if motor_key == "arl":
    st.caption(
        "La reserva RM está definida en el cálculo. Nombre Reserva no se expone "
        "porque el notebook no la lee desde la configuración."
    )

st.subheader("2. Archivos de entrada")
targets = required_inputs(engine_dir, folder, motor_key, motor, effective_config)
consolidated_names = consolidated_input_names(folder, motor["reserve"])
consolidated_dir = engine_dir / "inputs" / folder / "t_consolidada"
upload_columns = st.columns(2)
for column, name, label in zip(
    upload_columns,
    consolidated_names,
    ("Nuevo", "Stock"),
):
    with column:
        with st.container(border=True):
            st.markdown(f"#### Cargar {label}")
            st.caption(f"Nombre esperado: `{name}`")
            exists = (consolidated_dir / name).is_file()
            st.caption("Archivo cargado" if exists else "Pendiente de cargar")
            upload = st.file_uploader(
                f"Archivo {label}",
                type=["csv"],
                key=f"upload_{motor_key}_{folder}_{label.lower()}",
                label_visibility="collapsed",
                disabled=running or is_confirming_period,
            )
            if st.button(
                "Reemplazar archivo" if exists else "Cargar archivo",
                key=f"save_upload_{motor_key}_{folder}_{label.lower()}",
                disabled=running or is_confirming_period or upload is None,
                use_container_width=True,
            ):
                store_uploaded_file(consolidated_dir, name, upload.getvalue())
                st.success(f"Archivo guardado como {name}.")
                st.rerun()

other_targets = {
    name: directory
    for name, directory in targets.items()
    if name not in consolidated_names
}
missing = [
    name
    for name, directory in targets.items()
    if not (directory / name).is_file()
]
other_missing = [
    name for name in other_targets if name in missing
]
if other_missing:
    st.warning(
        "Faltan otros insumos obligatorios: " + ", ".join(other_missing)
    )

if other_targets:
    with st.expander("Cargar o reemplazar otros insumos obligatorios"):
        choice = st.selectbox(
            "Insumo", list(other_targets), key=f"other_upload_choice_{motor_key}"
        )
        upload = st.file_uploader(
            "Seleccione el archivo",
            type=[choice.rsplit(".", 1)[-1].lower()],
            key=f"other_upload_{motor_key}_{choice}",
            disabled=running or is_confirming_period,
        )
        if st.button(
            "Reemplazar insumo" if (other_targets[choice] / choice).is_file() else "Cargar insumo",
            disabled=running or is_confirming_period or upload is None,
            key=f"save_other_upload_{motor_key}",
        ):
            store_uploaded_file(other_targets[choice], choice, upload.getvalue())
            st.success(f"Archivo guardado como {choice}.")
            st.rerun()

manager_open_key = f"file_manager_open_{motor_key}"
if st.button(
    "Ver archivos cargados",
    key=f"toggle_file_manager_{motor_key}",
):
    st.session_state[manager_open_key] = not st.session_state.get(
        manager_open_key, False
    )

if st.session_state.get(manager_open_key, False):
    st.markdown("#### Archivos del periodo")
    area = st.selectbox(
        "Carpeta",
        ("parametros", "salida", "t_consolidada"),
        key=f"file_manager_area_{motor_key}",
        disabled=is_confirming_period,
    )
    area_dir = period_area_path(engine_dir, folder, area)
    period_files = sorted(
        path.relative_to(area_dir).as_posix()
        for path in area_dir.rglob("*")
        if path.is_file()
    ) if area_dir.exists() else []

    operation = st.session_state.get("file_manager_operation")
    if operation is not None and (
        operation["motor_key"] != motor_key
        or operation["folder"] != folder
        or operation["area"] != area
    ):
        st.session_state.pop("file_manager_operation", None)
        operation = None

    if not period_files:
        st.info(f"No hay archivos en inputs/{folder}/{area}.")
    else:
        relative_name = st.selectbox(
            "Archivo",
            period_files,
            key=f"file_manager_file_{motor_key}_{folder}_{area}",
            disabled=is_confirming_period,
        )
        file_path = resolve_period_file(
            engine_dir, folder, area, relative_name
        )
        if (
            operation is not None
            and operation["relative_name"] != relative_name
        ):
            st.session_state.pop("file_manager_operation", None)
            operation = None
        st.caption(
            f"{file_path.stat().st_size:,} bytes · "
            f"{file_path.relative_to(engine_dir).as_posix()}"
        )
        operation_matches = (
            operation is not None
            and operation["relative_name"] == relative_name
        )

        if not operation_matches:
            replace_column, remove_column = st.columns(2)
            disabled = running or is_confirming_period
            if replace_column.button(
                "Reemplazar",
                key=f"replace_file_{motor_key}_{folder}_{area}",
                disabled=disabled,
            ):
                st.session_state["file_manager_operation"] = {
                    "motor_key": motor_key,
                    "folder": folder,
                    "area": area,
                    "relative_name": relative_name,
                    "action": "replace",
                }
                st.rerun()
            if remove_column.button(
                "Quitar",
                key=f"remove_file_{motor_key}_{folder}_{area}",
                disabled=disabled,
            ):
                st.session_state["file_manager_operation"] = {
                    "motor_key": motor_key,
                    "folder": folder,
                    "area": area,
                    "relative_name": relative_name,
                    "action": "remove",
                }
                st.rerun()
        elif operation["action"] == "replace":
            st.warning(f"Se reemplazará `{relative_name}` conservando su nombre.")
            extension = Path(relative_name).suffix.lower().lstrip(".")
            replacement = st.file_uploader(
                "Seleccione el archivo de reemplazo",
                type=[extension] if extension else None,
                key=(
                    f"replacement_{motor_key}_{folder}_{area}_"
                    f"{relative_name.replace('/', '_')}"
                ),
                disabled=running or is_confirming_period,
            )
            confirm_column, cancel_column = st.columns(2)
            if confirm_column.button(
                "Confirmar reemplazo",
                key=f"confirm_replace_{motor_key}_{folder}_{area}",
                disabled=(
                    running
                    or is_confirming_period
                    or replacement is None
                ),
            ):
                target = resolve_period_file(
                    engine_dir, folder, area, relative_name
                )
                store_uploaded_file(
                    target.parent, target.name, replacement.getvalue()
                )
                st.session_state.pop("file_manager_operation", None)
                st.session_state["file_manager_message"] = (
                    f"Se reemplazó {relative_name}."
                )
                st.rerun()
            if cancel_column.button(
                "Cancelar",
                key=f"cancel_replace_{motor_key}_{folder}_{area}",
            ):
                st.session_state.pop("file_manager_operation", None)
                st.rerun()
        else:
            is_generated = (
                area == "salida"
                or "Sura" in relative_name
                or "Dummy" in relative_name
                or "nuevas_nuevas" in relative_name
            )
            st.warning(
                f"Se quitará `{relative_name}` permanentemente. "
                + (
                    "Este archivo puede haber sido generado por el motor. "
                    if is_generated
                    else ""
                )
                + "Esta acción no se puede deshacer desde la interfaz."
            )
            confirmed = st.checkbox(
                "Confirmo que deseo quitar este archivo",
                key=(
                    f"confirm_remove_{motor_key}_{folder}_{area}_"
                    f"{relative_name.replace('/', '_')}"
                ),
                disabled=running or is_confirming_period,
            )
            confirm_column, cancel_column = st.columns(2)
            if confirm_column.button(
                "Confirmar eliminación",
                key=f"delete_file_{motor_key}_{folder}_{area}",
                disabled=running or is_confirming_period or not confirmed,
            ):
                target = resolve_period_file(
                    engine_dir, folder, area, relative_name
                )
                target.unlink()
                st.session_state.pop("file_manager_operation", None)
                st.session_state["file_manager_message"] = (
                    f"Se quitó {relative_name}."
                )
                st.rerun()
            if cancel_column.button(
                "Cancelar",
                key=f"cancel_remove_{motor_key}_{folder}_{area}",
            ):
                st.session_state.pop("file_manager_operation", None)
                st.rerun()

manager_message = st.session_state.pop("file_manager_message", None)
if manager_message:
    st.success(manager_message)

st.subheader("3. Ejecución")
if missing:
    st.error("Faltan archivos de entrada; el cálculo no puede ejecutarse.")
if motor_key == "arl":
    if st.session_state.pop("clear_arl_password_next_run", False):
        st.session_state["arl_password"] = ""
    password_column, execute_column = st.columns([2, 1], vertical_alignment="bottom")
    with password_column:
        password = st.text_input(
            "Contraseña ARL",
            type="password",
            help="Se usa solo para esta ejecución; no se guarda en config ni logs.",
            key="arl_password",
            disabled=is_confirming_period,
        )
    with execute_column:
        run_clicked = st.button(
            "Ejecutar cálculo",
            type="primary",
            disabled=running or bool(missing) or not password.strip() or is_confirming_period,
            use_container_width=True,
        )
    if run_clicked:
        start_run(
            motor_key,
            engine_dir,
            str(motor["script"]),
            password,
        )
        st.session_state["clear_arl_password_next_run"] = True
        st.rerun()
else:
    if st.button(
        "Ejecutar cálculo",
        type="primary",
        disabled=running or bool(missing),
    ):
        start_run(motor_key, engine_dir, str(motor["script"]))
run_status(motor_key, engine_dir)

st.subheader("4. Resultados")
output_dir = engine_dir / "inputs" / folder / "salida"
files = sorted(path for path in output_dir.rglob("*") if path.is_file()) if output_dir.exists() else []
if not files:
    st.write("Todavía no hay resultados para este mes.")
for path in files:
    st.download_button(
        f"Descargar {path.relative_to(output_dir).as_posix()}",
        path.read_bytes(),
        file_name=path.name,
        key=f"download_{motor_key}_{path}",
    )
