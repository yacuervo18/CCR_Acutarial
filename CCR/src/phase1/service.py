"""Casos de uso de tablero y procesos."""
from .config import PROCESOS, con_tareas
from .domain import Alerta, EstadoProceso, ResumenProceso, TipoAlerta, derivar_estado, porcentaje_global
from .repository import Repository


class ProcessService:
    def __init__(self, repository: Repository) -> None:
        self.repository = repository

    def summaries(self, period: str) -> tuple[ResumenProceso, ...]:
        self.repository.ensure_period(period)
        summaries = []
        for definition in PROCESOS:
            process = con_tareas(definition, self.repository.completed(period, definition.codigo))
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
        alerts = []
        for s in summaries:
            if s.estado == EstadoProceso.BLOQUEADO:
                alerts.append(Alerta(TipoAlerta.BLOQUEADO, "Proceso bloqueado", s.proceso.nombre, "#888780"))
            if s.estado == EstadoProceso.VENCIDO:
                alerts.append(Alerta(TipoAlerta.VENCIDO, "Vencido", s.proceso.nombre, "#E24B4A"))
        return {"summaries": summaries, "avance": porcentaje_global(summaries), "kpis": {"pending": pending, "overdue": counts[EstadoProceso.VENCIDO], "blocked": counts[EstadoProceso.BLOQUEADO], "critical": 2, "sox": sox, "approvals": approvals}, "alerts": alerts}
