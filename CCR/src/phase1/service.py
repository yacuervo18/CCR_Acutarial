"""Casos de uso de tablero y procesos."""
from .config import PROCESOS, con_tareas
from datetime import date, datetime
import json
from .domain import Alerta, EstadoProceso, Proceso, ResumenProceso, Tarea, TipoAlerta, derivar_estado, porcentaje_global
from .notifications import Notification
from .repository import Repository


class ProcessService:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def summaries(self, period: str) -> tuple[ResumenProceso, ...]:
        self.repository.ensure_period(period)
        summaries = []
        for definition in PROCESOS:
            task_rows = self.repository.process_tasks(definition.codigo)
            tasks = tuple(
                Tarea(row["task_id"], row["name"], sox=bool(row["sox"]), requiere_aprobacion=bool(row["requires_approval"]))
                for row in task_rows
            )
            process = con_tareas(Proceso(
                definition.codigo, definition.nombre, definition.icono, definition.color,
                definition.descripcion, definition.guia, tasks, definition.fecha_limite, definition.bloqueado,
            ), self.repository.completed(period, definition.codigo))
            summaries.append(ResumenProceso(
                process,
                derivar_estado(process.tareas, process.fecha_limite, bloqueado=process.bloqueado),
                sum(t.completada for t in process.tareas),
                len(process.tareas),
            ))
        return tuple(summaries)

    def dashboard(self, period: str) -> dict:
        summaries = self.summaries(period)
        counts = {state: sum(s.estado == state for s in summaries) for state in EstadoProceso}
        pending = sum(s.total - s.completadas for s in summaries)
        sox = sum(1 for s in summaries for t in s.proceso.tareas if t.sox and not t.completada)
        approvals = sum(1 for s in summaries for t in s.proceso.tareas if t.requiere_aprobacion and not t.completada)
        alerts = self.central_alerts(period, summaries=summaries)
        return {"summaries": summaries, "avance": porcentaje_global(summaries), "kpis": {"pending": pending, "overdue": counts[EstadoProceso.VENCIDO], "blocked": counts[EstadoProceso.BLOQUEADO], "critical": 2, "sox": sox, "approvals": approvals}, "alerts": alerts}

    def central_alerts(self, period: str, *, summaries: tuple[ResumenProceso, ...] | None = None, now: datetime | None = None) -> list[Alerta]:
        """Consolida alertas operativas y programadas de todos los procesos."""
        now = now or datetime.now()
        summaries = summaries or self.summaries(period)
        alerts = []
        for summary in summaries:
            process = summary.proceso
            pending = [task for task in process.tareas if not task.completada]
            if summary.estado == EstadoProceso.BLOQUEADO:
                alerts.append(Alerta(TipoAlerta.BLOQUEADO, "Proceso bloqueado", process.nombre, "#888780"))
            if summary.estado == EstadoProceso.VENCIDO:
                alerts.append(Alerta(TipoAlerta.VENCIDO, "Proceso vencido", f"{process.nombre}: {len(pending)} tareas pendientes.", "#E24B4A"))
            sox_pending = sum(task.sox and not task.completada for task in process.tareas)
            approval_pending = sum(task.requiere_aprobacion and not task.completada for task in process.tareas)
            if sox_pending:
                alerts.append(Alerta(TipoAlerta.SOX, "Control SOX pendiente", f"{process.nombre}: {sox_pending} tarea(s) SOX.", "#BA7517"))
            if approval_pending:
                alerts.append(Alerta(TipoAlerta.APROBACION, "Aprobación pendiente", f"{process.nombre}: {approval_pending} tarea(s) requieren aprobación.", "#854F0B"))

            schedule = self.repository.process_schedule(process.codigo, period)
            if not schedule or not pending or summary.estado == EstadoProceso.COMPLETADO:
                continue
            if schedule["start_date"]:
                start = date.fromisoformat(schedule["start_date"])
                if start > now.date() and (start - now.date()).days <= 1:
                    alerts.append(Alerta(TipoAlerta.MASIVO, "Proceso próximo a iniciar", f"{process.nombre} inicia el {start.isoformat()}.", "#185FA5"))
                elif start <= now.date():
                    alerts.append(Alerta(TipoAlerta.MASIVO, "Proceso programado pendiente", f"{process.nombre}: {len(pending)} tarea(s) pendientes desde {start.isoformat()}.", "#E24B4A"))
            deadline_value = schedule["deadline_date"] if "deadline_date" in schedule.keys() else ""
            notice_days = int(schedule["notice_days"]) if "notice_days" in schedule.keys() else 2
            if deadline_value:
                deadline = date.fromisoformat(deadline_value)
                remaining = (deadline - now.date()).days
                if remaining < 0:
                    alerts.append(Alerta(TipoAlerta.VENCIDO, "Proceso vencido", f"{process.nombre}: venció el {deadline.isoformat()} y tiene {len(pending)} tarea(s) pendientes.", "#E24B4A"))
                elif remaining <= notice_days:
                    alerts.append(Alerta(TipoAlerta.VENCIDO, "Próximo vencimiento", f"{process.nombre}: faltan {remaining} día(s) para vencer el {deadline.isoformat()}.", "#BA7517"))
        return alerts

    def daily_reminders(self, period: str, now: datetime | None = None) -> list[Notification]:
        """Obtiene recordatorios vencidos para hoy; no repite uno ya registrado."""
        now = now or datetime.now()
        reminders = []
        for summary in self.summaries(period):
            schedule = self.repository.process_schedule(summary.proceso.codigo, period)
            if not schedule or summary.estado == EstadoProceso.COMPLETADO:
                continue
            if schedule["start_date"] and now.date().isoformat() < schedule["start_date"]:
                continue
            if now.month not in json.loads(schedule["months"]):
                continue
            scheduled_days = json.loads(schedule["days"]) if "days" in schedule.keys() else []
            if scheduled_days and now.day not in scheduled_days:
                continue
            if now.strftime("%H:%M") < schedule["scheduled_time"] or not self.repository.reminder_due(summary.proceso.codigo, period, now, schedule["interval_minutes"]):
                continue
            recipients = json.loads(schedule["recipients"])
            emails = tuple(item["value"] for item in recipients)
            reminders.append(Notification(summary.proceso.codigo, period, "recordatorio_pendiente", f"{summary.proceso.nombre}: {summary.total - summary.completadas} actividades pendientes", emails, "Teams", now.isoformat()))
        return reminders
