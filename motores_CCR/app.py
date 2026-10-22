"""Interfaz común para los motores actuariales de CCR."""

import os
import shutil
import subprocess
import sys
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
        "parameter_names": (
            "Fecha valoración t-1",
            "Fecha valoración t",
            "Fecha Cierre",
            "SMMLV",
            "Inflacion",
            "Salida",
            "Mortalidad",
            "Informe",
            "Correr Nuevas",
            "Conservar Mesada",
            "bd_t_1",
            "Flujos_proyectados",
        ),
    },
}


def selected_motor() -> tuple[str, MotorDefinition]:
    requested = st.query_params.get("motor", "ley100").lower()
    if requested not in MOTORS:
        st.warning("Ese motor aún no está disponible. Se seleccionó Ley 100.")
        requested = "ley100"

    labels = {motor["label"]: key for key, motor in MOTORS.items()}
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
        f"{folder}_t_consolidada_Nuevo_{reserve}.csv": root / "t_consolidada",
        f"{folder}_t_consolidada_Stock_{reserve}.csv": root / "t_consolidada",
        "hip_deslizamiento.csv": root / "parametros",
        "rx_cambio_grupo.csv": root / "parametros",
    }
    if motor_key == "arl":
        targets.update(
            {
                f"{folder}_t_consolidada_Sura_{reserve}.csv": root / "t_consolidada",
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

    log_file = engine_dir / "logs" / "ultima_ejecucion.log"
    if log_file.exists():
        st.code(
            log_file.read_text(encoding="utf-8", errors="replace")[-6000:]
            or "(sin salida todavía)"
        )


st.set_page_config(page_title="Motores CCR", layout="wide")
st.title("Motores actuariales CCR")
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
parameter_names = motor["parameter_names"]
visible_config = (
    config
    if parameter_names is None
    else config[config["Parametro"].isin(parameter_names)].copy()
)
edited = st.data_editor(
    visible_config,
    disabled=True if is_confirming_period else ["Parametro"],
    hide_index=True,
    width="stretch",
    height=420,
    key=f"config_editor_{motor_key}",
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
    disabled=running or is_confirming_period,
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
missing = []
for name, directory in targets.items():
    exists = (directory / name).exists()
    st.write(
        ("✅ " if exists else "❌ ")
        + f"{directory.relative_to(engine_dir).as_posix()}/{name}"
    )
    if not exists:
        missing.append(name)

with st.expander("Cargar o reemplazar archivos"):
    choice = st.selectbox("Archivo", list(targets), key=f"upload_choice_{motor_key}")
    upload = st.file_uploader("Seleccione el archivo", key=f"upload_{motor_key}_{choice}")
    if upload is not None and st.button(
        "Guardar archivo", disabled=running, key=f"save_upload_{motor_key}"
    ):
        target = targets[choice]
        target.mkdir(parents=True, exist_ok=True)
        (target / choice).write_bytes(upload.getvalue())
        st.success(f"Archivo guardado: {choice}.")
        st.rerun()

st.subheader("3. Ejecución")
if missing:
    st.error("Faltan archivos de entrada; el cálculo no puede ejecutarse.")
if motor_key == "arl":
    with st.form(f"execute_form_{motor_key}", clear_on_submit=True):
        password_column, execute_column = st.columns([2, 1])
        with password_column:
            password = st.text_input(
                "Contraseña ARL",
                type="password",
                help="Se usa solo para esta ejecución; no se guarda en config ni logs.",
                key="arl_password",
            )
        with execute_column:
            submitted = st.form_submit_button(
                "Ejecutar cálculo",
                type="primary",
                disabled=running or bool(missing),
            )
    if submitted:
        start_run(
            motor_key,
            engine_dir,
            str(motor["script"]),
            password,
        )
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
