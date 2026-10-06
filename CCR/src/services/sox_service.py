"""
Servicio de controles SOX.
"""
from datetime import date
from typing import Optional
from src.database.db_manager import execute_query, execute_one, execute_insert, execute_update
from src.services.config_service import get_estados_activos


def get_controles_sox_cierre(cierre_id: int) -> list[dict]:
    rows = execute_query("""
        SELECT cs.*, e.codigo as estado_codigo, e.nombre as estado_nombre, e.color as estado_color,
               u.nombre as responsable_nombre
        FROM controles_sox cs
        JOIN estados e ON cs.estado_id = e.id
        LEFT JOIN usuarios u ON cs.responsable_id = u.id
        WHERE cs.cierre_id = ? AND cs.activo = 1
        ORDER BY cs.orden
    """, (cierre_id,))
    
    controles = []
    for row in rows:
        # Calcular estado automático "Vencido"
        estado_calc = row["estado_codigo"]
        if row["fecha_ejecucion"] and estado_calc not in ("completado", "cancelado"):
            fecha_ejec = date.fromisoformat(row["fecha_ejecucion"])
            if fecha_ejec < date.today():
                estado_calc = "vencido"
        
        controles.append({
            **dict(row),
            "estado_calculado": estado_calc,
            "vencido": estado_calc == "vencido"
        })
    return controles


def get_control_sox_by_id(control_id: int) -> Optional[dict]:
    row = execute_one("""
        SELECT cs.*, e.codigo as estado_codigo, e.nombre as estado_nombre, e.color as estado_color,
               u.nombre as responsable_nombre
        FROM controles_sox cs
        JOIN estados e ON cs.estado_id = e.id
        LEFT JOIN usuarios u ON cs.responsable_id = u.id
        WHERE cs.id = ? AND cs.activo = 1
    """, (control_id,))
    return dict(row) if row else None


def crear_control_sox(
    cierre_id: int,
    nombre: str,
    descripcion: str = "",
    responsable_id: Optional[int] = None,
    fecha_ejecucion: Optional[str] = None,
    estado_codigo: str = "pendiente",
    observaciones: str = "",
    orden: int = 0
) -> tuple[bool, str]:
    estado = execute_one("SELECT id FROM estados WHERE codigo = ?", (estado_codigo,))
    if not estado:
        return False, "Estado inválido."
    
    try:
        execute_insert(
            """INSERT INTO controles_sox (cierre_id, nombre, descripcion, responsable_id, fecha_ejecucion, estado_id, observaciones, orden)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (cierre_id, nombre, descripcion, responsable_id, fecha_ejecucion, estado["id"], observaciones, orden)
        )
        return True, "Control SOX creado."
    except Exception as e:
        return False, f"Error: {e}"


def actualizar_control_sox(control_id: int, **kwargs) -> bool:
    campos = ["nombre", "descripcion", "responsable_id", "fecha_ejecucion", "estado_id", "observaciones", "orden"]
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in campos and v is not None:
            updates.append(f"{k} = ?")
            params.append(v)
    if not updates:
        return False
    updates.append("actualizado_en = datetime('now')")
    params.append(control_id)
    return execute_update(f"UPDATE controles_sox SET {', '.join(updates)} WHERE id = ?", tuple(params)) > 0


def get_submodulos_sox() -> list[str]:
    """Submódulos SOX predefinidos."""
    return ["Bitácoras SOX", "Parametrización", "Pantallazos", "Conciliaciones", "Validaciones", "Aprobaciones SOX"]