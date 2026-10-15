"""Exportación del estado operativo para integraciones externas."""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import tempfile

from .service import ProcessService


DEFAULT_NOTIFICATIONS_DIR = (
    Path.home() / "OneDrive - Seguros Suramericana, S.A" / "Notificaciones"
)


def notifications_directory() -> Path:
    configured = os.environ.get("CCR_NOTIFICATIONS_DIR", "").strip()
    return Path(configured) if configured else DEFAULT_NOTIFICATIONS_DIR


def export_status(service: ProcessService, period: str, now: datetime | None = None) -> Path:
    """Write the selected period status as an atomic JSON file."""
    now = now or datetime.now()
    dashboard = service.dashboard(period)
    processes = []
    central_alerts = service.central_alerts(period, now=now)

    for summary in dashboard["summaries"]:
        schedule = service.repository.process_schedule(summary.proceso.codigo, period)
        pending_tasks = [
            {
                "id": task.id,
                "nombre": task.nombre,
                "sox": task.sox,
                "requiere_aprobacion": task.requiere_aprobacion,
            }
            for task in summary.proceso.tareas
            if not task.completada
        ]
        schedule_data = None
        if schedule:
            schedule_data = {
                "fecha_inicio": schedule["start_date"],
                "hora": schedule["scheduled_time"],
                "meses": json.loads(schedule["months"]),
                "dias_del_mes": json.loads(schedule["days"]) if "days" in schedule.keys() else [],
                "intervalo_minutos": schedule["interval_minutes"],
                "fecha_limite": schedule["deadline_date"] if "deadline_date" in schedule.keys() else "",
                "dias_aviso_previo": schedule["notice_days"] if "notice_days" in schedule.keys() else 2,
                "destinatarios": json.loads(schedule["recipients"]),
                "canal": schedule["channel"],
            }
        process_alerts = [
            {
                "tipo": alert.tipo.value,
                "titulo": alert.titulo,
                "descripcion": alert.descripcion,
            }
            for alert in central_alerts
            if summary.proceso.nombre in alert.descripcion or alert.descripcion == summary.proceso.nombre
        ]
        processes.append(
            {
                "codigo": summary.proceso.codigo,
                "nombre": summary.proceso.nombre,
                "estado": summary.estado.value,
                "completadas": summary.completadas,
                "total_tareas": summary.total,
                "pendientes": pending_tasks,
                "bloqueado": summary.estado.value == "Bloqueado",
                "vencido": summary.estado.value == "Vencido",
                "completado": summary.estado.value == "Completado",
                "programacion": schedule_data,
                "alertas": process_alerts,
                "debe_notificar": bool(process_alerts) and schedule_data is not None,
            }
        )

    payload = {
        "version": 1,
        "generado_en": now.isoformat(timespec="seconds"),
        "periodo": period,
        "avance_global": dashboard["avance"],
        "indicadores": dashboard["kpis"],
        "alertas": [
            {
                "tipo": alert.tipo.value,
                "titulo": alert.titulo,
                "descripcion": alert.descripcion,
            }
            for alert in central_alerts
        ],
        "procesos": processes,
    }

    directory = notifications_directory()
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / "estado_ccr.json"
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=directory,
        prefix=".estado_ccr.",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        json.dump(payload, temporary, ensure_ascii=False, indent=2)
        temporary.write("\n")
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, destination)
    return destination
