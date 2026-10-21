"""Interfaz del Motor Ley 100.

Capa externa: edita los archivos de configuracion, carga insumos, lanza
motor_ley100.py como subproceso y muestra el log y las salidas. No contiene
ninguna formula del calculo.
"""
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILES = ("config_cierre.txt", "config.txt")
SCRIPT = BASE_DIR / "motor_ley100.py"
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "ultima_ejecucion.log"
NOMBRE_RESERVA = "Ley100"

st.set_page_config(page_title="Motor Ley 100", page_icon="⚖️", layout="wide")


def read_config() -> pd.DataFrame:
    return pd.read_csv(BASE_DIR / CONFIG_FILES[0], sep=";", dtype=str, keep_default_na=False)


def save_config(df: pd.DataFrame) -> None:
    for name in CONFIG_FILES:
        df.to_csv(BASE_DIR / name, sep=";", index=False, encoding="utf-8", lineterminator="\n")


def month_folder(config: pd.DataFrame) -> str:
    values = dict(zip(config["Parametro"], config["Valor"]))
    year, month, *_ = values["Fecha Cierre"].split("/")
    return f"{year}{month}"


def required_inputs(folder: str) -> dict[str, Path]:
    root = BASE_DIR / "inputs" / folder
    return {
        f"{folder}_t_consolidada_Nuevo_{NOMBRE_RESERVA}.csv": root / "t_consolidada",
        f"{folder}_t_consolidada_Stock_{NOMBRE_RESERVA}.csv": root / "t_consolidada",
        "hip_deslizamiento.csv": root / "parametros",
        "rx_cambio_grupo.csv": root / "parametros",
    }


def is_running() -> bool:
    process = st.session_state.get("process")
    return process is not None and process.poll() is None


def start_run() -> None:
    LOG_DIR.mkdir(exist_ok=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
    log = open(LOG_FILE, "w", encoding="utf-8")
    st.session_state["process"] = subprocess.Popen(
        [sys.executable, str(SCRIPT)], cwd=BASE_DIR, stdout=log, stderr=subprocess.STDOUT, env=env
    )


@st.fragment(run_every=3)
def run_status() -> None:
    process = st.session_state.get("process")
    if process is None:
        st.info("Aún no se ha ejecutado el motor en esta sesión.")
        return
    code = process.poll()
    if code is None:
        st.warning("Ejecutando el cálculo. Puede tardar varios minutos; no cierre esta ventana.")
    elif code == 0:
        st.success("El cálculo terminó correctamente.")
    else:
        st.error(f"El cálculo terminó con error (código {code}). Revise el log.")
    if LOG_FILE.exists():
        st.code(LOG_FILE.read_text(encoding="utf-8", errors="replace")[-6000:] or "(sin salida todavía)")


st.title("⚖️ Motor Ley 100")
st.caption("Reserva matemática Ley 100. Ejecuta motor_ley100.py, conversión fiel de motor_Ley100.ipynb.")

config = read_config()
folder = month_folder(config)

st.subheader("1. Parámetros")
edited = st.data_editor(
    config,
    disabled=["Parametro"],
    hide_index=True,
    width="stretch",
    height=420,
    key="config_editor",
)
if st.button("Guardar parámetros", disabled=is_running()):
    save_config(edited)
    st.success("Parámetros guardados en config_cierre.txt y config.txt.")
    st.rerun()
st.caption(
    f"Carpeta de trabajo según Fecha Cierre: inputs/{folder}. "
    "Los valores fijos dentro del cálculo (por ejemplo SMMLV) solo cambian en motor_ley100.py."
)

st.subheader("2. Archivos de entrada")
missing = []
for name, directory in required_inputs(folder).items():
    exists = (directory / name).exists()
    st.write(("✅ " if exists else "❌ ") + f"{directory.relative_to(BASE_DIR).as_posix()}/{name}")
    if not exists:
        missing.append(name)

with st.expander("Cargar o reemplazar archivos"):
    targets = required_inputs(folder)
    choice = st.selectbox("Archivo", list(targets))
    upload = st.file_uploader("Seleccione el archivo", key=f"up_{choice}")
    if upload is not None and st.button("Guardar archivo", disabled=is_running()):
        target = targets[choice]
        target.mkdir(parents=True, exist_ok=True)
        (target / choice).write_bytes(upload.getvalue())
        st.success(f"Guardado como {choice}.")
        st.rerun()

st.subheader("3. Ejecución")
if missing:
    st.error("Faltan archivos de entrada; el cálculo no puede ejecutarse.")
if st.button("Ejecutar cálculo", type="primary", disabled=is_running() or bool(missing)):
    start_run()
run_status()

st.subheader("4. Resultados")
salida = BASE_DIR / "inputs" / folder / "salida"
files = sorted(p for p in salida.rglob("*") if p.is_file()) if salida.exists() else []
if not files:
    st.write("Todavía no hay resultados para este mes.")
for path in files:
    st.download_button(
        f"Descargar {path.relative_to(salida).as_posix()}",
        path.read_bytes(),
        file_name=path.name,
        key=f"dl_{path}",
    )
