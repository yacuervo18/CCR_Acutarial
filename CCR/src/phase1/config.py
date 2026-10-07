"""Configuración central de procesos y tareas por defecto."""
from dataclasses import replace
from datetime import date
from .domain import Proceso, Tarea


PROCESOS: tuple[Proceso, ...] = (
    Proceso("rentabilidades", "Rentabilidades", "📈", "#639922", "Actualizar y validar las rentabilidades mensuales.", ("Recopilar tasas de mercado", "Actualizar curvas", "Validar consistencia", "Generar reporte"), tuple(Tarea(i, n, sox=i == 3) for i, n in enumerate(("Recopilar tasas de mercado", "Actualizar curvas de rentabilidad", "Validar consistencia", "Generar reporte"), 1))),
    Proceso("indices", "Índices y monedas", "💱", "#185FA5", "Actualizar índices económicos y tasas de cambio.", ("Descargar fuentes oficiales", "Validar fuentes", "Publicar insumos"), tuple(Tarea(i, n) for i, n in enumerate(("Descargar índices oficiales", "Actualizar tasas de cambio", "Validar fuentes", "Publicar en repositorio"), 1))),
    Proceso("f394", "F394", "📄", "#BA7517", "Preparar el reporte mensual F394.", ("Actualizar insumos", "Programar ramos", "Revisar ejecución", "Validar generación"), tuple(Tarea(i, n, requiere_aprobacion=i == 3) for i, n in enumerate(("Actualizar rentabilidades", "Programar ramo 087", "Revisar ejecución", "Validar generación", "Documentar cambios"), 1))),
    Proceso("salario_minimo", "Reserva de salario mínimo", "🧮", "#854F0B", "Ejecutar la reserva asociada al salario mínimo.", ("Preparar población", "Ejecutar cálculo", "Revisar resultados", "Solicitar aprobación"), tuple(Tarea(i, n, sox=i == 3, requiere_aprobacion=i == 4) for i, n in enumerate(("Preparar población", "Ejecutar cálculo", "Revisar resultados", "Solicitar aprobación"), 1))),
    Proceso("rbns", "Reserva siniestros avisados (RBNS)", "🛡️", "#A32D2D", "Actualizar la reserva de siniestros avisados.", ("Cargar siniestros", "Clasificar casos", "Validar reserva"), tuple(Tarea(i, n) for i, n in enumerate(("Cargar siniestros", "Clasificar casos", "Validar reserva", "Aprobar resultados"), 1))),
    Proceso("rm_ley_100", "RM Ley 100", "⚖️", "#185FA5", "Ejecutar y documentar la reserva matemática Ley 100.", ("Preparar datos", "Ejecutar reserva", "Conciliar resultados"), tuple(Tarea(i, n, sox=i == 3) for i, n in enumerate(("Preparar datos", "Ejecutar reserva", "Conciliar resultados", "Documentar soporte", "Obtener aprobación"), 1))),
    Proceso("rm_conmutacion", "RM Conmutación", "🔁", "#639922", "Gestionar la reserva de conmutación.", ("Validar solicitudes", "Calcular valores", "Revisar soporte"), tuple(Tarea(i, n) for i, n in enumerate(("Validar solicitudes", "Calcular valores", "Revisar soporte", "Cerrar proceso"), 1))),
    Proceso("rm_arl", "RM ARL", "🏥", "#E24B4A", "Gestionar la reserva ARL y sus correcciones.", ("Cargar información", "Aplicar reglas ARL", "Validar resultados"), tuple(Tarea(i, n, requiere_aprobacion=i == 4) for i, n in enumerate(("Cargar información", "Aplicar reglas ARL", "Validar resultados", "Aplicar correcciones", "Aprobar cierre"), 1))),
)


def proceso_por_codigo(codigo: str) -> Proceso:
    return next(p for p in PROCESOS if p.codigo == codigo)


def con_tareas(proceso: Proceso, completadas: set[int]) -> Proceso:
    return replace(proceso, tareas=tuple(replace(t, completada=t.id in completadas) for t in proceso.tareas))
