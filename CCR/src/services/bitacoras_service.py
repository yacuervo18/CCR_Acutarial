"""
Servicio de bitácoras - Registro inmutable de eventos.
"""
from datetime import datetime
from typing import Optional
from src.database.db_manager import execute_insert, execute_query, transaction


def registrar_bitacora(
    usuario: str,
    proceso_id: Optional[int] = None,
    subtarea_id: Optional[int] = None,
    control_sox_id: Optional[int] = None,
    aprobacion_id: Optional[int] = None,
    comentario: str = ""
) -> int:
    """Registra una entrada en la bitácora (inmutable)."""
    return execute_insert(
        """INSERT INTO bitacoras (fecha, usuario, proceso_id, subtarea_id, control_sox_id, aprobacion_id, comentario)
           VALUES (datetime('now'), ?, ?, ?, ?, ?, ?)""",
        (usuario, proceso_id, subtarea_id, control_sox_id, aprobacion_id, comentario)
    )


def get_bitacoras_proceso(proceso_id: int) -> list[dict]:
    rows = execute_query("""
        SELECT * FROM bitacoras
        WHERE proceso_id = ?
        ORDER BY fecha DESC
    """, (proceso_id,))
    return [dict(row) for row in rows]


def get_bitacoras_subtarea(subtarea_id: int) -> list[dict]:
    rows = execute_query("""
        SELECT * FROM bitacoras
        WHERE subtarea_id = ?
        ORDER BY fecha DESC
    """, (subtarea_id,))
    return [dict(row) for row in rows]


def get_bitacoras_global(
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    proceso_id: Optional[int] = None,
    usuario: Optional[str] = None,
    limite: int = 100
) -> list[dict]:
    """Consulta global de bitácoras con filtros."""
    conditions = []
    params = []
    
    if fecha_desde:
        conditions.append("fecha >= ?")
        params.append(fecha_desde)
    if fecha_hasta:
        conditions.append("fecha <= ?")
        params.append(fecha_hasta)
    if proceso_id:
        conditions.append("proceso_id = ?")
        params.append(proceso_id)
    if usuario:
        conditions.append("usuario = ?")
        params.append(usuario)
    
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params.append(limite)
    
    rows = execute_query(f"""
        SELECT b.*, p.nombre as proceso_nombre
        FROM bitacoras b
        LEFT JOIN procesos p ON b.proceso_id = p.id
        {where}
        ORDER BY b.fecha DESC
        LIMIT ?
    """, tuple(params))
    return [dict(row) for row in rows]