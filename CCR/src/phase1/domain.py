"""Modelos y reglas puras de la fase 1."""
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum


class EstadoProceso(str, Enum):
    PENDIENTE = "Pendiente"
    EN_PROCESO = "En proceso"
    VENCIDO = "Vencido"
    BLOQUEADO = "Bloqueado"
    PENDIENTE_APROBACION = "Pendiente aprobación"
    COMPLETADO = "Completado"


class TipoAlerta(str, Enum):
    BLOQUEADO = "Proceso bloqueado"
    VENCIDO = "Vencido"
    SOX = "Control SOX pendiente"
    MASIVO = "Proceso masivo próximo"


@dataclass(frozen=True)
class Tarea:
    id: int
    nombre: str
    completada: bool = False
    sox: bool = False
    requiere_aprobacion: bool = False


@dataclass(frozen=True)
class Proceso:
    codigo: str
    nombre: str
    icono: str
    color: str
    descripcion: str
    guia: tuple[str, ...]
    tareas: tuple[Tarea, ...]
    fecha_limite: date | None = None
    bloqueado: bool = False


@dataclass(frozen=True)
class ResumenProceso:
    proceso: Proceso
    estado: EstadoProceso
    completadas: int
    total: int


@dataclass(frozen=True)
class Alerta:
    tipo: TipoAlerta
    titulo: str
    descripcion: str
    color: str


def derivar_estado(
    tareas: tuple[Tarea, ...],
    fecha_limite: date | None = None,
    *,
    bloqueado: bool = False,
    aprobacion_pendiente: bool = False,
    hoy: date | None = None,
) -> EstadoProceso:
    """Deriva el estado sin persistirlo como dato independiente."""
    hoy = hoy or date.today()
    if bloqueado:
        return EstadoProceso.BLOQUEADO
    if tareas and all(t.completada for t in tareas):
        return EstadoProceso.COMPLETADO
    if aprobacion_pendiente:
        return EstadoProceso.PENDIENTE_APROBACION
    if fecha_limite and fecha_limite < hoy:
        return EstadoProceso.VENCIDO
    return EstadoProceso.EN_PROCESO if any(t.completada for t in tareas) else EstadoProceso.PENDIENTE


def porcentaje_global(procesos: tuple[ResumenProceso, ...]) -> int:
    """Calcula el avance ponderado por cantidad de tareas."""
    total = sum(p.total for p in procesos)
    return round(sum(p.completadas for p in procesos) * 100 / total) if total else 0
