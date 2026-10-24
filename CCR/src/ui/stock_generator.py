"""UI and subprocess boundary for the isolated RM stock generator."""
from __future__ import annotations

import calendar
import json
import os
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import streamlit as st

from . import consolidated_review, original_bundle

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
    process: subprocess.Popen[str] | _CompletedProcess
    log_path: Path
    tipo_ramo: str
    periodo: str
    params: dict[str, Any]
    review_requested: bool = False
    completed_event: dict[str, Any] | None = None
    recovered: bool = False


class _CompletedProcess:
    def poll(self) -> int:
        return 0


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

    job = GeneratorJob(
        process,
        log_path,
        tipo_ramo,
        periodo,
        dict(payload["params"]),
        payload.get("revisar_antes_de_partir") is True,
    )
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


def _generated_file_paths(job: GeneratorJob) -> dict[str, Path]:
    ramo_folder = "Ley100" if job.tipo_ramo == "LEY100" else "ARL"
    suffix = "Ley100" if job.tipo_ramo == "LEY100" else "RM"
    output_dir = GENERATOR_ROOT / ramo_folder / job.periodo / "6_Ts_consolidadas"
    return {
        "Total": output_dir / f"{job.periodo}_t_consolidada_{suffix}.csv",
        "Stock": output_dir / f"{job.periodo}_t_consolidada_Stock_{suffix}.csv",
        "Nuevo": output_dir / f"{job.periodo}_t_consolidada_Nuevo_{suffix}.csv",
    }


def _read_run_manifest(job: GeneratorJob) -> tuple[Path, dict[str, Any]]:
    total_path = _generated_file_paths(job)["Total"]
    manifest_path = total_path.parent / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"No se pudo leer el registro de generación: {error}") from error
    if not isinstance(manifest, dict):
        raise ValueError("El registro de generación tiene un formato inválido.")
    return manifest_path, manifest


def _review_paths(
    job: GeneratorJob, manifest: dict[str, Any]
) -> tuple[str, Path, Path]:
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str) or len(run_id) != 32 or not run_id.isalnum():
        raise ValueError("El registro de generación no contiene un identificador válido.")
    output_dir = _generated_file_paths(job)["Total"].parent
    reviewed_name = f"{job.periodo}_t_consolidada_Ley100_revisado_{run_id}.csv"
    audit_name = f"{job.periodo}_correcciones_{run_id}.jsonl"
    registered_name = manifest.get("archivo_revisado")
    if registered_name not in (None, reviewed_name):
        raise ValueError("El consolidado revisado no corresponde a la corrida activa.")
    return run_id, output_dir / reviewed_name, output_dir / audit_name


def _recover_completed_review_job(code: str) -> GeneratorJob | None:
    branch = RAMOS[code]
    if branch["tipo"] != "LEY100":
        return None

    saved = load_branch_params(code)
    period = str(saved["fecha_valoracion"]).replace("-", "")[:6]
    output_dir = GENERATOR_ROOT / "Ley100" / period / "6_Ts_consolidadas"
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"No se pudo recuperar el registro de generación: {error}") from error
    if not isinstance(manifest, dict):
        raise ValueError("El registro de generación tiene un formato inválido.")
    if manifest.get("estado") != "consolidado_total":
        return None

    run_id = manifest.get("run_id")
    if not isinstance(run_id, str) or len(run_id) != 32 or not run_id.isalnum():
        raise ValueError("El registro de generación no contiene un identificador válido.")
    total_path = output_dir / f"{period}_t_consolidada_Ley100.csv"
    if not total_path.is_file():
        raise ValueError("El registro indica un consolidado total, pero falta el archivo.")

    review_requested = (
        manifest.get("revision_habilitada") is True
        or bool(manifest.get("archivo_revisado"))
        or int(manifest.get("cantidad_correcciones", 0)) > 0
    )
    if not review_requested:
        return None

    cutoff = manifest.get("fecha_corte_vigencia")
    valuation_date = manifest.get("fecha_valoracion_t")
    if not isinstance(cutoff, str) or not isinstance(valuation_date, str):
        raise ValueError("Al registro de generación le faltan fechas para continuar.")
    params = {
        "fecha_valoracion": valuation_date,
        "fecha_minima_prod_nueva": cutoff[:7].replace("-", ""),
        "inflacion": manifest.get("inflacion"),
        "smmlv": manifest.get("smmlv"),
        "interes_real": manifest.get("interes_real"),
        "ramo": branch["ramo"],
        "compania": branch["compania"],
        "fecha_corte_vigencia": cutoff,
        "stock_vacia": manifest.get("stock_vacia", False),
        "nuevo_vacia": manifest.get("nuevo_vacia", False),
    }
    return GeneratorJob(
        _CompletedProcess(),
        RUN_LOGS / f"{branch['tipo']}_{period}_recuperado.jsonl",
        branch["tipo"],
        period,
        params,
        review_requested=True,
        completed_event={
            "type": "completed",
            "total": str(total_path),
            "stock": None,
            "nuevo": None,
        },
        recovered=True,
    )


def _write_run_manifest(path: Path, manifest: dict[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _render_generated_downloads(job: GeneratorJob, completed: dict[str, Any]) -> None:
    files = _generated_file_paths(job)
    try:
        _, manifest = _read_run_manifest(job)
        if job.tipo_ramo == "LEY100":
            _, reviewed_path, _ = _review_paths(job, manifest)
        else:
            reviewed_path = None
            if manifest.get("archivo_revisado"):
                raise ValueError("ARL no admite revisiones de pólizas en esta fase.")
    except ValueError as error:
        st.error(str(error))
        return
    available = []
    for file_type in ("Total", "Stock", "Nuevo"):
        path = files[file_type]
        if file_type == "Total" and not completed.get("total"):
            continue
        if file_type in {"Stock", "Nuevo"} and not completed.get(file_type.lower()):
            continue
        if not path.is_file():
            st.error(f"El proceso reportó {file_type}, pero no se encontró el archivo esperado: {path}")
            continue
        label = (
            "Total original"
            if file_type == "Total" and manifest.get("archivo_revisado")
            else file_type
        )
        available.append((label, path, file_type.lower()))
    if manifest.get("archivo_revisado"):
        if reviewed_path is not None and reviewed_path.is_file():
            available.append(("Total revisado", reviewed_path, "filas_total"))
        else:
            st.error("El manifest referencia un consolidado revisado que no existe o no corresponde al ramo.")

    if not available:
        st.warning("No hay archivos consolidados disponibles para descargar.")
        return

    columns = st.columns(len(available))
    count_keys = {
        "Total": "filas_total",
        "Total original": "filas_total",
        "Stock": "filas_stock",
        "Nuevo": "filas_nuevo",
    }
    for column, (label, path, count_key) in zip(columns, available):
        with column:
            count = manifest.get(count_keys.get(label, count_key))
            if count is not None:
                st.caption(f"{label} · {count:,} filas")
            st.download_button(
                f"Descargar {label}",
                data=path.read_bytes(),
                file_name=path.name,
                mime="text/csv",
                key=f"download-stock-{job.tipo_ramo}-{job.periodo}-{label.lower()}",
                use_container_width=True,
            )

    if completed.get("stock") and completed.get("nuevo"):
        run_id = manifest.get("run_id")
        if not isinstance(run_id, str) or len(run_id) != 32 or not run_id.isalnum():
            st.error("No se puede preparar Ts_original: el registro no identifica la corrida.")
            return
        archive_path = files["Total"].parent / f"Ts_original_{job.periodo}_{run_id}.zip"
        st.caption(
            "El ZIP reúne el total final, Stock completo de evidencia, Nuevo, "
            "la macro calculada y las T1 a T11 en XLSX."
        )
        if st.button(
            "Preparar paquete Ts_original (.zip)",
            key=f"prepare-ts-original-{job.tipo_ramo}-{job.periodo}-{run_id}",
        ):
            ramo_folder = "Ley100" if job.tipo_ramo == "LEY100" else "ARL"
            suffix = "Ley100" if job.tipo_ramo == "LEY100" else "RM"
            try:
                archive_path = original_bundle.create_original_bundle(
                    GENERATOR_ROOT,
                    ramo_folder,
                    job.periodo,
                    suffix,
                    manifest,
                )
            except (OSError, ValueError, zipfile.BadZipFile) as error:
                st.error(f"No se pudo preparar el paquete Ts_original: {error}")
            else:
                st.success("Paquete Ts_original preparado con las salidas, la macro y las Ts.")
        if archive_path.is_file():
            size_mb = archive_path.stat().st_size / (1024 * 1024)
            st.caption(f"Paquete · {size_mb:.1f} MB")
            with archive_path.open("rb") as archive_file:
                st.download_button(
                    "Descargar Ts_original (.zip)",
                    data=archive_file,
                    file_name=archive_path.name,
                    mime="application/zip",
                    key=f"download-ts-original-{job.tipo_ramo}-{job.periodo}-{run_id}",
                    use_container_width=True,
                )


def _render_review_editor(job: GeneratorJob) -> None:
    files = _generated_file_paths(job)
    try:
        manifest_path, manifest = _read_run_manifest(job)
        run_id, reviewed_path, audit_path = _review_paths(job, manifest)
    except ValueError as error:
        st.error(str(error))
        return

    if not files["Total"].is_file():
        st.error("No se encontró el consolidado total para buscar pólizas.")
        return
    registered_revision = manifest.get("archivo_revisado")
    if registered_revision and not reviewed_path.is_file():
        st.error("El registro indica que hay correcciones, pero falta el archivo revisado.")
        return
    source_path = reviewed_path if registered_revision else files["Total"]
    prefix = f"stock-review-{job.periodo}-{run_id}"
    search_key = f"{prefix}-query"
    results_key = f"{prefix}-results"
    token_key = f"{prefix}-search-token"

    with st.expander("Buscar y corregir una póliza", expanded=True):
        st.caption(
            "Busca por NMPOLIZA. El total original se conserva; cada ajuste queda "
            "en una copia revisada de esta corrida y no se reaplica al regenerar."
        )
        with st.form(f"{prefix}-search-form"):
            policy_query = st.text_input("Número de póliza (NMPOLIZA)", key=search_key)
            search_submitted = st.form_submit_button("Buscar póliza")
        if search_submitted:
            try:
                headers, matches = consolidated_review.find_policy_rows(
                    source_path, policy_query
                )
            except (OSError, ValueError) as error:
                st.error(f"No se pudo buscar la póliza: {error}")
                st.session_state.pop(results_key, None)
            else:
                st.session_state[results_key] = {
                    "headers": headers,
                    "matches": matches,
                    "query": policy_query.strip(),
                }
                st.session_state[token_key] = uuid4().hex

        results = st.session_state.get(results_key)
        if results:
            matches = results["matches"]
            if not matches:
                st.info(f"No se encontró la póliza {results['query']} en el consolidado.")
            else:
                st.success(f"Se encontraron {len(matches)} registro(s) para esa póliza.")
                row_by_index = {index: row for index, row in matches}
                token = st.session_state.get(token_key, "initial")

                def describe_match(row_index: int) -> str:
                    row = row_by_index[row_index]
                    context = [f"Registro {row_index + 1}"]
                    for column in ("Asegurado", "FEVIGENCIA_INICIAL", "Estado Póliza"):
                        if row.get(column):
                            context.append(f"{column}: {row[column]}")
                    return " · ".join(context)

                selected_row_index = st.selectbox(
                    "Registro de la póliza",
                    options=[index for index, _ in matches],
                    format_func=describe_match,
                    key=f"{prefix}-{token}-row",
                )
                row = row_by_index[selected_row_index]
                with st.expander("Ver todos los datos de esta póliza"):
                    st.json(row)
                editable_columns = [
                    column
                    for column in results["headers"]
                    if column not in consolidated_review.READ_ONLY_COLUMNS
                ]
                if not editable_columns:
                    st.error("No hay columnas editables en el consolidado.")
                else:
                    field = st.selectbox(
                        "Campo que deseas corregir",
                        options=editable_columns,
                        key=f"{prefix}-{token}-{selected_row_index}-field",
                    )
                    current_value = row.get(field, "")
                    st.caption(
                        f"Valor actual de **{field}**: "
                        f"{current_value if current_value else '(vacío)'}"
                    )
                    new_value = st.text_input(
                        "Nuevo valor",
                        value=current_value,
                        key=f"{prefix}-{token}-{selected_row_index}-{field}-value",
                        help="Se guarda como texto. Revisa el formato requerido para fechas y números.",
                    )
                    if st.button(
                        "Guardar corrección para esta corrida",
                        key=f"{prefix}-{token}-{selected_row_index}-save",
                        type="primary",
                    ):
                        if new_value == current_value:
                            st.info("El valor no cambió; no se guardó ninguna corrección.")
                        else:
                            try:
                                previous_value = consolidated_review.update_reviewed_cell(
                                    source_path,
                                    reviewed_path,
                                    selected_row_index,
                                    field,
                                    new_value,
                                )
                                correction = {
                                    "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
                                    "run_id": run_id,
                                    "NMPOLIZA": row["NMPOLIZA"],
                                    "fila_csv": selected_row_index + 2,
                                    "columna": field,
                                    "valor_anterior": previous_value,
                                    "valor_nuevo": new_value,
                                }
                                consolidated_review.append_change_record(audit_path, correction)
                                manifest["archivo_revisado"] = reviewed_path.name
                                manifest["cantidad_correcciones"] = (
                                    int(manifest.get("cantidad_correcciones", 0)) + 1
                                )
                                manifest["revision_actualizada_en"] = correction["fecha"]
                                _write_run_manifest(manifest_path, manifest)
                            except (OSError, ValueError, IndexError, TypeError) as error:
                                st.error(f"No se pudo guardar la corrección: {error}")
                            else:
                                row[field] = new_value
                                st.session_state[results_key] = results
                                st.success("Corrección guardada en la copia revisada de esta corrida.")
                                st.rerun(scope="app")

        if audit_path.is_file():
            st.caption(
                f"Correcciones registradas en esta corrida: "
                f"{manifest.get('cantidad_correcciones', 0)}."
            )
            st.download_button(
                "Descargar bitácora de correcciones",
                data=audit_path.read_bytes(),
                file_name=audit_path.name,
                mime="application/x-ndjson",
                key=f"{prefix}-download-audit",
            )


def _render_job_monitor_content(key: str) -> None:
    job = _JOBS.get(key)
    if job is None:
        return
    events = _read_events(job.log_path)
    progress_event = next(
        (event for event in reversed(events) if event.get("type") == "progress"),
        None,
    )
    completed = job.completed_event or next(
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
        if completed.get("stock") and completed.get("nuevo"):
            st.success("t_consolidada generada. Los archivos quedaron en generador_t; no se copiaron al motor.")
        else:
            st.info(
                "Consolidado total generado. Puedes buscar una póliza, guardar correcciones "
                "para esta corrida y luego generar Stock/Nuevo."
            )
            if job.review_requested and job.tipo_ramo == "LEY100":
                try:
                    manifest_path, manifest = _read_run_manifest(job)
                    if manifest.get("revision_habilitada") is not True:
                        manifest["revision_habilitada"] = True
                        _write_run_manifest(manifest_path, manifest)
                except (OSError, ValueError, TypeError) as error:
                    st.error(f"No se pudo guardar el estado de revisión: {error}")
            if job.recovered:
                st.caption("Se recuperó esta corrida desde los archivos guardados.")
        _render_generated_downloads(job, completed)
        if (
            job.review_requested
            and job.tipo_ramo == "LEY100"
            and completed.get("total")
            and not completed.get("stock")
            and not completed.get("nuevo")
        ):
            _render_review_editor(job)
        if completed.get("total") and not completed.get("stock") and not completed.get("nuevo"):
            has_corrections = False
            if job.review_requested and job.tipo_ramo == "LEY100":
                try:
                    _, manifest = _read_run_manifest(job)
                    has_corrections = int(manifest.get("cantidad_correcciones", 0)) > 0
                except (ValueError, TypeError) as error:
                    st.error(f"No se pudo verificar el estado de las correcciones: {error}")
            if st.button(
                "Aplicar correcciones y generar Stock/Nuevo"
                if has_corrections
                else "Continuar y generar Stock/Nuevo",
                key=f"continue-stock-{key.lower()}-{job.periodo}",
                type="primary",
            ):
                try:
                    start_generator(
                        {
                            "action": "split",
                            "tipo_ramo": job.tipo_ramo,
                            "params": job.params,
                        }
                    )
                except (OSError, RuntimeError, ValueError, KeyError) as error:
                    st.error(f"No se pudo continuar la generación: {error}")
                else:
                    st.rerun(scope="app")
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
    if return_code is not None:
        st.caption("Esto solo oculta el resultado en pantalla; no borra la bitácora ni los archivos.")
        if st.button(
            "Descartar resultado anterior",
            key=f"discard-stock-result-{key.replace(':', '-')}-{job.periodo}",
            on_click=_discard_job_result,
            args=(key,),
        ):
            return


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
    # Solo considera que hay archivos si existe manifest completo (generación válida)
    manifest_path = period_dir / "6_Ts_consolidadas" / "manifest.json"
    return period_dir.is_dir() and manifest_path.is_file()


def _clear_credentials(code: str) -> None:
    for suffix in ("usuario", "contrasena_osiris", "contrasena_macro"):
        st.session_state[f"stock-{code}-{suffix}"] = ""


def _discard_job_result(key: str) -> None:
    job = _JOBS.get(key)
    if job is not None and job.process.poll() is not None:
        _JOBS.pop(key)


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
    if job is None:
        try:
            job = _recover_completed_review_job(code)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
            st.error(f"No se pudo recuperar la revisión guardada: {error}")
        else:
            if job is not None:
                _JOBS[job_key] = job
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
                    close_cols = st.columns(3)
                    with close_cols[0]:
                        fecha_valoracion = st.date_input(
                            "Fecha de cierre",
                            value=close_date,
                            key=f"stock-{code}-fecha",
                        )
                    selected_close_date = fecha_valoracion
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
                    else:
                        st.info(
                            f"No hay archivos para este ramo y período ({period_month}). "
                            "Puede continuar con la parametrización manual."
                        )
                    if not GENERATOR_PYTHON.is_file():
                        st.info("El formulario se puede revisar, pero no iniciar hasta preparar el entorno.")

                    with st.form(f"stock-{code}-form"):
                        dates = st.columns(3)
                        with dates[0]:
                            fecha_minima = st.date_input(
                                "Fecha mínima de nueva producción (T11)",
                                value=min_date,
                                key=f"stock-{code}-minima",
                                help="Se guarda como AAAAMM.",
                            )
                        with dates[1]:
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
                                help=(
                                    "El Stock sale solo con encabezados y el cálculo corre más rápido. "
                                    "Las pólizas anteriores al corte quedan solo en el consolidado total."
                                ),
                            )
                            # En Ley 100 Nuevo siempre lleva pólizas.
                            nuevo_vacia = False
                            if branch["tipo"] != "LEY100":
                                nuevo_vacia = st.checkbox(
                                    "Generar Nuevo vacío (solo encabezados)",
                                    value=bool(initial["nuevo_vacia"]),
                                    key=f"stock-{code}-nuevo-vacio",
                                )
                        revisar_antes_de_partir = False
                        if branch["tipo"] == "LEY100":
                            revisar_antes_de_partir = st.checkbox(
                                "Revisar el consolidado total antes de partir Stock/Nuevo",
                                key=f"stock-{code}-revisar-total",
                                help=(
                                    "Detiene la generación después de guardar el consolidado total "
                                    "para buscar y corregir pólizas antes de partir Stock/Nuevo."
                                ),
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
                                "revisar_antes_de_partir": revisar_antes_de_partir,
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
