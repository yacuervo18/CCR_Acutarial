"""UI and subprocess boundary for the isolated RM stock generator."""
from __future__ import annotations

import calendar
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from uuid import uuid4

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[3]
GENERATOR_ROOT = PROJECT_ROOT / "generador_t"
GENERATOR_PYTHON = GENERATOR_ROOT / ".venv" / "Scripts" / "python.exe"
PARAMS_PATH = GENERATOR_ROOT / "params.json"
RUN_LOGS = GENERATOR_ROOT / "run_logs"

RAMOS = {
    "rm_arl": {
        "tipo": "ARL",
        "nombre": "ARL",
        "ramo": "094",
        "compania": "22",
        "fecha_minima_prod_nueva": "202301",
        "fecha_corte_vigencia": "2023-01-01",
    },
    "rm_ley_100": {
        "tipo": "LEY100",
        "nombre": "Ley 100",
        "ramo": "087",
        "compania": "02",
        "fecha_minima_prod_nueva": "202408",
        "fecha_corte_vigencia": "2024-08-01",
    },
}


@dataclass
class GeneratorJob:
    process: subprocess.Popen[str]
    log_path: Path
    tipo_ramo: str
    periodo: str


_JOBS: dict[str, GeneratorJob] = {}


def _job_key(tipo_ramo: str) -> str:
    return tipo_ramo


def _default_close_date() -> date:
    today = date.today()
    return date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])


def _read_config(path: Path = PARAMS_PATH) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"La configuración debe ser un objeto JSON: {path}")
    return data


def load_branch_params(code: str, path: Path = PARAMS_PATH) -> dict[str, Any]:
    branch = RAMOS[code]
    config = _read_config(path)
    if "ramo_activo" in config:
        common = config.get("ARL") or config.get("LEY100") or {}
    else:
        common = config
    if not isinstance(common, dict):
        raise ValueError(f"Los parámetros compartidos del archivo no son válidos: {path}")

    saved = config.get(branch["tipo"], {})
    if not isinstance(saved, dict):
        raise ValueError(f"Los parámetros de {branch['nombre']} no son válidos: {path}")
    defaults = {
        "fecha_valoracion": _default_close_date().isoformat(),
        "inflacion": 6.14,
        "smmlv": 1750905.0,
        "interes_real": 4.0,
        "fecha_minima_prod_nueva": branch["fecha_minima_prod_nueva"],
        "fecha_corte_vigencia": branch["fecha_corte_vigencia"],
        "stock_vacia": False,
        "nuevo_vacia": False,
    }
    values = {**defaults}
    for key in ("fecha_valoracion", "inflacion", "smmlv", "interes_real"):
        if key in common:
            values[key] = common[key]
    values.update(saved)
    values["ramo"] = branch["ramo"]
    values["compania"] = branch["compania"]
    values["tipo_ramo"] = branch["tipo"]
    date.fromisoformat(str(values["fecha_valoracion"]))
    date.fromisoformat(str(values["fecha_corte_vigencia"]))
    minimum_month = str(values["fecha_minima_prod_nueva"])
    if len(minimum_month) != 6 or not minimum_month.isdigit():
        raise ValueError("La fecha mínima de nueva producción debe tener formato AAAAMM.")
    date(int(minimum_month[:4]), int(minimum_month[4:]), 1)
    return values


def save_branch_params(code: str, values: dict[str, Any], path: Path = PARAMS_PATH) -> None:
    branch = RAMOS[code]
    config = _read_config(path)
    if "ramo_activo" not in config:
        config = {"ramo_activo": "ARL", "ARL": config}
    params = {
        "fecha_valoracion": values["fecha_valoracion"],
        "fecha_minima_prod_nueva": values["fecha_minima_prod_nueva"],
        "inflacion": float(values["inflacion"]),
        "smmlv": float(values["smmlv"]),
        "interes_real": float(values["interes_real"]),
        "ramo": branch["ramo"],
        "compania": branch["compania"],
        "fecha_corte_vigencia": values["fecha_corte_vigencia"],
        "stock_vacia": bool(values["stock_vacia"]),
        "nuevo_vacia": bool(values["nuevo_vacia"]),
    }
    config["ramo_activo"] = branch["tipo"]
    config[branch["tipo"]] = params
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(config, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def start_generator(payload: dict[str, Any]) -> GeneratorJob:
    if not GENERATOR_PYTHON.is_file():
        raise FileNotFoundError(
            f"No existe {GENERATOR_PYTHON}. Ejecuta generador_t\\instalar.bat."
        )
    RUN_LOGS.mkdir(parents=True, exist_ok=True)
    tipo_ramo = payload["tipo_ramo"]
    periodo = str(payload["params"]["fecha_valoracion"]).replace("-", "")[:6]
    log_path = RUN_LOGS / f"{tipo_ramo}_{periodo}_{uuid4().hex}.jsonl"
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    child_environment = os.environ.copy()
    child_environment["PYTHONIOENCODING"] = "utf-8"

    with log_path.open("w", encoding="utf-8", newline="\n") as log_file:
        process = subprocess.Popen(
            [str(GENERATOR_PYTHON), "-m", "core.worker"],
            cwd=GENERATOR_ROOT,
            stdin=subprocess.PIPE,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            creationflags=creationflags,
            env=child_environment,
        )
        if process.stdin is None:
            process.terminate()
            raise RuntimeError("No se pudo abrir el canal privado del proceso.")
        try:
            process.stdin.write(json.dumps(payload, ensure_ascii=False))
            process.stdin.close()
        except OSError:
            if process.poll() is None:
                process.terminate()
            raise RuntimeError(
                f"No se pudo enviar la solicitud al proceso. Bitácora: {log_path.name}"
            ) from None

    job = GeneratorJob(process, log_path, tipo_ramo, periodo)
    _JOBS[_job_key(tipo_ramo)] = job
    return job


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("rb") as log_file:
        log_file.seek(0, os.SEEK_END)
        size = log_file.tell()
        log_file.seek(max(0, size - 96 * 1024))
        content = log_file.read().decode("utf-8", errors="replace")
    lines = content.splitlines()
    if size > 96 * 1024 and lines:
        lines = lines[1:]
    events = []
    for line in lines[-200:]:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _render_job_monitor_content(key: str) -> None:
    job = _JOBS.get(key)
    if job is None:
        return
    events = _read_events(job.log_path)
    progress_event = next(
        (event for event in reversed(events) if event.get("type") == "progress"),
        None,
    )
    completed = next(
        (event for event in reversed(events) if event.get("type") == "completed"),
        None,
    )
    error = next(
        (event for event in reversed(events) if event.get("type") == "error"),
        None,
    )
    return_code = job.process.poll()

    if return_code is None:
        st.info(f"Generando t_consolidada para {job.tipo_ramo} · {job.periodo}.")
        if progress_event:
            current = int(progress_event.get("current", 0))
            total = int(progress_event.get("total", 0))
            fraction = min(max(current / total, 0.0), 1.0) if total else 0.0
            st.progress(
                fraction,
                text=f"{progress_event.get('step', 'Proceso')}: "
                f"{progress_event.get('message', 'En curso')}",
            )
    elif return_code == 0 and completed:
        st.success("t_consolidada generada. Los archivos quedaron en generador_t; no se copiaron al motor.")
        st.caption(f"Stock: {completed.get('stock', '')}")
        st.caption(f"Nuevo: {completed.get('nuevo', '')}")
    elif error:
        st.error(str(error.get("message", "La generación falló.")))
    else:
        st.error(
            f"El proceso terminó con código {return_code} sin reportar resultado. "
            f"Revisa la bitácora {job.log_path.name}."
        )

    log_messages = [
        f"[{event.get('timestamp', '')}] {event['message']}"
        for event in events
        if event.get("type") == "log" and event.get("message")
    ]
    if job.log_path.is_file():
        with st.expander("Bitácora de ejecución", expanded=return_code is None):
            st.code("\n".join(log_messages[-30:]) or "No hay eventos estructurados en la bitácora.")
            st.download_button(
                "Descargar bitácora",
                data=job.log_path.read_bytes(),
                file_name=job.log_path.name,
                mime="application/json",
                key=f"download-stock-log-{key.replace(':', '-')}",
            )


@st.fragment(run_every="2s")
def _render_live_job_monitor(key: str) -> None:
    job = _JOBS.get(key)
    if job is not None and job.process.poll() is not None:
        st.rerun(scope="app")
        return
    _render_job_monitor_content(key)


def _period_has_files(code: str, month: str) -> bool:
    branch_folder = "Ley100" if RAMOS[code]["tipo"] == "LEY100" else "ARL"
    period_dir = GENERATOR_ROOT / branch_folder / month
    return period_dir.is_dir() and any(period_dir.iterdir())


def _clear_credentials(code: str) -> None:
    for suffix in ("usuario", "contrasena_osiris", "contrasena_macro"):
        st.session_state[f"stock-{code}-{suffix}"] = ""


def render_stock_generator(code: str, readonly: bool) -> None:
    branch = RAMOS[code]
    st.markdown(
        '<div class="ccr-process-extension">'
        '<div class="ccr-process-extension-title">Generar t_consolidada</div>'
        '<div class="ccr-process-extension-copy">'
        "Descarga y consolida las tablas en un proceso separado. Sus archivos "
        "quedan en la carpeta del generador y no se pasan automáticamente al motor."
        "</div></div>",
        unsafe_allow_html=True,
    )

    clear_key = f"stock-{code}-clear-credentials"
    if st.session_state.pop(clear_key, False):
        _clear_credentials(code)

    state_key = f"stock-{code}-show-form"
    job_key = _job_key(branch["tipo"])
    job = _JOBS.get(job_key)
    running_job = next(
        (item for item in _JOBS.values() if item.process.poll() is None),
        None,
    )
    active = running_job is not None
    if job is not None:
        if job.process.poll() is None:
            _render_live_job_monitor(job_key)
        else:
            _render_job_monitor_content(job_key)
    if running_job is not None and running_job is not job:
        st.info(
            f"Ya hay una generación de {running_job.tipo_ramo} en curso "
            f"para {running_job.periodo}. Espera a que termine antes de iniciar otra."
        )

    with st.container(key=f"stock-generator-{code}"):
        if not st.session_state.get(state_key, False) and not active:
            if st.button(
                "Configurar generación",
                key=f"stock-{code}-open",
                disabled=readonly,
                use_container_width=True,
            ):
                st.session_state[state_key] = True
                st.rerun()
        elif st.session_state.get(state_key, False) and not active:
            with st.container(border=True):
                st.markdown(f"### Parámetros · {branch['nombre']}")
                if readonly:
                    st.warning("Los periodos históricos son de solo lectura.")
                if not GENERATOR_PYTHON.is_file():
                    st.warning(
                        "Falta el entorno del generador. Ejecuta "
                        "`generador_t\\instalar.bat` una vez en este equipo."
                    )

                try:
                    initial = load_branch_params(code)
                    close_date = date.fromisoformat(initial["fecha_valoracion"])
                    cutoff_date = date.fromisoformat(initial["fecha_corte_vigencia"])
                    min_month = str(initial["fecha_minima_prod_nueva"])
                    min_date = date(int(min_month[:4]), int(min_month[4:]), 1)
                except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
                    st.error(f"No se pudieron leer los parámetros del generador: {error}")
                    initial = None

                if initial is not None:
                    selected_close_date = st.session_state.get(
                        f"stock-{code}-fecha", close_date
                    )
                    if not isinstance(selected_close_date, date):
                        selected_close_date = close_date
                    period_month = selected_close_date.strftime("%Y%m")
                    already_has_files = _period_has_files(code, period_month)
                    if already_has_files:
                        st.warning(
                            "Ya hay archivos para este ramo y periodo. La ejecución "
                            "no borra la carpeta, pero puede reemplazar archivos con "
                            "el mismo nombre. Revisa la bitácora y confirma antes de continuar."
                        )
                    if not GENERATOR_PYTHON.is_file():
                        st.info("El formulario se puede revisar, pero no iniciar hasta preparar el entorno.")

                    with st.form(f"stock-{code}-form"):
                        dates = st.columns(3)
                        with dates[0]:
                            fecha_valoracion = st.date_input(
                                "Fecha de cierre",
                                value=close_date,
                                key=f"stock-{code}-fecha",
                            )
                        with dates[1]:
                            fecha_minima = st.date_input(
                                "Fecha mínima de nueva producción (T11)",
                                value=min_date,
                                key=f"stock-{code}-minima",
                                help="Se guarda como AAAAMM.",
                            )
                        with dates[2]:
                            fecha_corte = st.date_input(
                                "Fecha de corte Stock/Nuevo",
                                value=cutoff_date,
                                key=f"stock-{code}-corte",
                            )

                        st.caption(
                            f"Ramo {branch['ramo']} · Compañía {branch['compania']} "
                            "· estos códigos quedan fijados según el proceso."
                        )
                        values = st.columns(3)
                        with values[0]:
                            inflacion = st.number_input(
                                "Inflación (%)",
                                value=float(initial["inflacion"]),
                                format="%.4f",
                                key=f"stock-{code}-inflacion",
                            )
                        with values[1]:
                            smmlv = st.number_input(
                                "SMMLV",
                                value=float(initial["smmlv"]),
                                step=1000.0,
                                format="%.0f",
                                key=f"stock-{code}-smmlv",
                            )
                        with values[2]:
                            interes_real = st.number_input(
                                "Interés real (%)",
                                value=float(initial["interes_real"]),
                                format="%.4f",
                                key=f"stock-{code}-interes",
                            )

                        with st.expander("Opciones de salida"):
                            stock_vacia = st.checkbox(
                                "Generar Stock vacío (solo encabezados)",
                                value=bool(initial["stock_vacia"]),
                                key=f"stock-{code}-stock-vacio",
                            )
                            nuevo_vacia = st.checkbox(
                                "Generar Nuevo vacío (solo encabezados)",
                                value=bool(initial["nuevo_vacia"]),
                                key=f"stock-{code}-nuevo-vacio",
                            )

                        st.markdown("**Credenciales temporales**")
                        usuario = st.text_input(
                            "Usuario Osiris/SURA",
                            key=f"stock-{code}-usuario",
                        )
                        contrasena_osiris = st.text_input(
                            "Contraseña Osiris/SURA",
                            type="password",
                            key=f"stock-{code}-contrasena_osiris",
                        )
                        contrasena_macro = st.text_input(
                            "Contraseña de la macro",
                            type="password",
                            key=f"stock-{code}-contrasena_macro",
                        )
                        st.caption(
                            "Las credenciales se envían al proceso hijo por entrada estándar; "
                            "no se guardan en parámetros ni en la bitácora."
                        )
                        confirmation_text = (
                            "Confirmo que revisé los archivos existentes y autorizo "
                            "reemplazar los de igual nombre al generar este periodo."
                            if already_has_files
                            else "Confirmo los parámetros y autorizo iniciar la generación."
                        )
                        confirmed = st.checkbox(
                            confirmation_text,
                            key=f"stock-{code}-confirm-{period_month}",
                        )
                        submitted = st.form_submit_button(
                            "Confirmar y generar",
                            type="primary",
                            disabled=readonly or active or not GENERATOR_PYTHON.is_file(),
                            use_container_width=True,
                        )

                    if submitted:
                        if not usuario or not contrasena_osiris or not contrasena_macro:
                            st.error("Completa las tres credenciales para continuar.")
                        elif not confirmed:
                            st.error("Confirma los parámetros antes de iniciar.")
                        else:
                            params = {
                                "fecha_valoracion": fecha_valoracion.isoformat(),
                                "fecha_minima_prod_nueva": fecha_minima.strftime("%Y%m"),
                                "inflacion": inflacion,
                                "smmlv": smmlv,
                                "interes_real": interes_real,
                                "ramo": branch["ramo"],
                                "compania": branch["compania"],
                                "fecha_corte_vigencia": fecha_corte.isoformat(),
                                "stock_vacia": stock_vacia,
                                "nuevo_vacia": nuevo_vacia,
                            }
                            request = {
                                "tipo_ramo": branch["tipo"],
                                "params": params,
                                "credentials": {
                                    "usuario_osiris": usuario,
                                    "contrasena_osiris": contrasena_osiris,
                                    "contrasena_macro": contrasena_macro,
                                },
                            }
                            try:
                                save_branch_params(code, params)
                                job = start_generator(request)
                            except (OSError, RuntimeError, ValueError, KeyError) as error:
                                st.session_state[f"stock-{code}-launch-error"] = str(error)
                            else:
                                st.session_state[state_key] = False
                            st.session_state[clear_key] = True
                            st.rerun()

                    launch_error = st.session_state.pop(
                        f"stock-{code}-launch-error", None
                    )
                    if launch_error:
                        st.error(f"No se pudo iniciar la generación: {launch_error}")

                if st.button("Cerrar parámetros", key=f"stock-{code}-close"):
                    st.session_state[state_key] = False
                    st.session_state[clear_key] = True
                    st.rerun()
