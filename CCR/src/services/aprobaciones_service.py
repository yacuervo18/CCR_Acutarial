"""
Servicio de aprobaciones.
"""
from datetime import date
from typing import Optional
from src.database.db_manager import execute_query, execute_one, execute_insert, execute_update
from src.services.config_service import get_estados_activos


def get_aprobaciones_cierre(cierre_id: int) -> list[dict]:
    rows = execute_query("""
        SELECT a.*, 
               et.codigo as estado_tecnico_codigo, et.nombre as estado_tecnico_nombre, et.color as estado_tecnico_color,
               ea.codigo as estado_aprobacion_codigo, ea.nombre as estado_aprobacion_nombre, ea.color as estado_aprobacion_color,
               es.codigo as estado_sox_codigo, es.nombre as estado_sox_nombre, es.color as estado_sox_color,
               u.nombre as responsable_nombre, p.nombre as proceso_nombre
        FROM aprobaciones a
        JOIN estados et ON a.estado_tecnico_id = et.id
        JOIN estados ea ON a.estado_aprobacion_id = ea.id
        JOIN estados es ON a.estado_sox_id = es.id
        LEFT JOIN usuarios u ON a.responsable_id = u.id
        LEFT JOIN procesos p ON a.proceso_id = p.id
        WHERE a.cierre_id = ? AND a.activo = 1
        ORDER BY a.creado_en
    """, (cierre_id,))
    
    aprobaciones = []
    for row in rows:
        # Verificar si todos los estados están completados
        estados_completados = all(
            row[f"estado_{s}_codigo"] == "completado" 
            for s in ["tecnico", "aprobacion", "sox"]
        )
        aprobaciones.append({
            **dict(row),
            "completada_totalmente": estados_completados
        })
    return aprobaciones


def get_aprobacion_by_id(aprobacion_id: int) -> Optional[dict]:
    row = execute_one("""
        SELECT a.*, 
               et.codigo as estado_tecnico_codigo, et.nombre as estado_tecnico_nombre, et.color as estado_tecnico_color,
               ea.codigo as estado_aprobacion_codigo, ea.nombre as estado_aprobacion_nombre, ea.color as estado_aprobacion_color,
               es.codigo as estado_sox_codigo, es.nombre as estado_sox_nombre, es.color as estado_sox_color,
               u.nombre as responsable_nombre, u.email as responsable_email
        FROM aprobaciones a
        JOIN estados et ON a.estado_tecnico_id = et.id
        JOIN estados ea ON a.estado_aprobacion_id = ea.id
        JOIN estados es ON a.estado_sox_id = es.id
        LEFT JOIN usuarios u ON a.responsable_id = u.id
        WHERE a.id = ? AND a.activo = 1
    """, (aprobacion_id,))
    return dict(row) if row else None


def crear_aprobacion(
    cierre_id: int,
    nombre: str,
    proceso_id: Optional[int] = None,
    responsable_id: Optional[int] = None,
    estado_tecnico_codigo: str = "pendiente",
    estado_aprobacion_codigo: str = "pendiente",
    estado_sox_codigo: str = "pendiente",
    observaciones: str = ""
) -> tuple[bool, str]:
    for codigo in [estado_tecnico_codigo, estado_aprobacion_codigo, estado_sox_codigo]:
        estado = execute_one("SELECT id FROM estados WHERE codigo = ?", (codigo,))
        if not estado:
            return False, f"Estado inválido: {codigo}"
    
    try:
        execute_insert(
            """INSERT INTO aprobaciones 
               (cierre_id, proceso_id, nombre, estado_tecnico_id, estado_aprobacion_id, estado_sox_id, responsable_id, observaciones)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (cierre_id, proceso_id, nombre,
             execute_one("SELECT id FROM estados WHERE codigo = ?", (estado_tecnico_codigo,))["id"],
             execute_one("SELECT id FROM estados WHERE codigo = ?", (estado_aprobacion_codigo,))["id"],
             execute_one("SELECT id FROM estados WHERE codigo = ?", (estado_sox_codigo,))["id"],
             responsable_id, observaciones)
        )
        return True, "Aprobación creada."
    except Exception as e:
        return False, f"Error: {e}"


def actualizar_aprobacion(aprobacion_id: int, **kwargs) -> bool:
    campos = ["nombre", "proceso_id", "responsable_id", "estado_tecnico_id", "estado_aprobacion_id", "estado_sox_id", 
              "fecha_envio", "fecha_aprobacion", "observaciones"]
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in campos and v is not None:
            updates.append(f"{k} = ?")
            params.append(v)
    if not updates:
        return False
    updates.append("actualizado_en = datetime('now')")
    params.append(aprobacion_id)
    return execute_update(f"UPDATE aprobaciones SET {', '.join(updates)} WHERE id = ?", tuple(params)) > 0


def puede_completar_reserva(aprobacion_id: int) -> bool:
    """Verifica si los tres estados están completados."""
    row = execute_one("""
        SELECT et.codigo as tec, ea.codigo as apr, es.codigo as sox
        FROM aprobaciones a
        JOIN estados et ON a.estado_tecnico_id = et.id
        JOIN estados ea ON a.estado_aprobacion_id = ea.id
        JOIN estados es ON a.estado_sox_id = es.id
        WHERE a.id = ?
    """, (aprobacion_id,))
    if row:
        return all(c == "completado" for c in [row["tec"], row["apr"], row["sox"]])
    return False