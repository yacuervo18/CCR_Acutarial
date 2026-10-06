"""
Servicio de procesos masivos.
"""
from datetime import date, datetime
from typing import Optional
from src.database.db_manager import execute_query, execute_one, execute_insert, execute_update, transaction
from src.services.config_service import get_estados_activos


def get_procesos_masivos(
    fecha_desde: Optional[str] = None,
    fecha_hasta: Optional[str] = None,
    estado_codigo: Optional[str] = None,
    ramo: Optional[str] = None
) -> list[dict]:
    conditions = ["activo = 1"]
    params = []
    
    if fecha_desde:
        conditions.append("fecha_ejecucion >= ?")
        params.append(fecha_desde)
    if fecha_hasta:
        conditions.append("fecha_ejecucion <= ?")
        params.append(fecha_hasta)
    if estado_codigo:
        estado = execute_one("SELECT id FROM estados WHERE codigo = ?", (estado_codigo,))
        if estado:
            conditions.append("estado_id = ?")
            params.append(estado["id"])
    if ramo:
        conditions.append("ramo = ?")
        params.append(ramo)
    
    where = "WHERE " + " AND ".join(conditions)
    
    rows = execute_query(f"""
        SELECT pm.*, e.codigo as estado_codigo, e.nombre as estado_nombre, e.color as estado_color
        FROM procesos_masivos pm
        JOIN estados e ON pm.estado_id = e.id
        {where}
        ORDER BY pm.fecha_ejecucion, pm.hora
    """, tuple(params))
    return [dict(row) for row in rows]


def get_proceso_masivo_by_id(pm_id: int) -> Optional[dict]:
    row = execute_one("""
        SELECT pm.*, e.codigo as estado_codigo, e.nombre as estado_nombre, e.color as estado_color
        FROM procesos_masivos pm
        JOIN estados e ON pm.estado_id = e.id
        WHERE pm.id = ? AND pm.activo = 1
    """, (pm_id,))
    return dict(row) if row else None


def crear_proceso_masivo(
    codigo: str,
    nombre: str,
    fecha_ejecucion: str,
    hora: Optional[str] = None,
    ramo: Optional[str] = None,
    estado_codigo: str = "pendiente",
    observaciones: str = ""
) -> tuple[bool, str]:
    """Crea un proceso masivo. Retorna (exito, mensaje)."""
    # Verificar duplicado
    exists = execute_one(
        "SELECT 1 FROM procesos_masivos WHERE codigo = ? AND fecha_ejecucion = ? AND (ramo = ? OR (ramo IS NULL AND ? IS NULL))",
        (codigo, fecha_ejecucion, ramo, ramo)
    )
    if exists:
        return False, "Ya existe un proceso masivo con ese código, fecha y ramo."
    
    estado = execute_one("SELECT id FROM estados WHERE codigo = ?", (estado_codigo,))
    if not estado:
        return False, "Estado inválido."
    
    try:
        execute_insert(
            """INSERT INTO procesos_masivos (codigo, nombre, fecha_ejecucion, hora, ramo, estado_id, observaciones)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (codigo, nombre, fecha_ejecucion, hora, ramo, estado["id"], observaciones)
        )
        return True, "Proceso masivo creado."
    except Exception as e:
        return False, f"Error: {e}"


def actualizar_proceso_masivo(pm_id: int, **kwargs) -> bool:
    campos = ["codigo", "nombre", "fecha_ejecucion", "hora", "ramo", "estado_id", "observaciones"]
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in campos and v is not None:
            updates.append(f"{k} = ?")
            params.append(v)
    if not updates:
        return False
    updates.append("actualizado_en = datetime('now')")
    params.append(pm_id)
    return execute_update(f"UPDATE procesos_masivos SET {', '.join(updates)} WHERE id = ?", tuple(params)) > 0


def get_procesos_masivos_proximos(dias: int = 7) -> list[dict]:
    hoy = date.today()
    limite = (hoy + timedelta(days=dias)).isoformat()
    hoy_iso = hoy.isoformat()
    
    rows = execute_query("""
        SELECT pm.*, e.codigo as estado_codigo, e.nombre as estado_nombre, e.color as estado_color
        FROM procesos_masivos pm
        JOIN estados e ON pm.estado_id = e.id
        WHERE pm.activo = 1
        AND pm.fecha_ejecucion BETWEEN ? AND ?
        AND e.codigo NOT IN ('completado', 'cancelado')
        ORDER BY pm.fecha_ejecucion, pm.hora
    """, (hoy_iso, limite))
    return [dict(row) for row in rows]


def importar_csv_procesos_masivos(csv_path: str) -> dict:
    """Importa procesos masivos desde CSV. Retorna stats."""
    import pandas as pd
    
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return {"exito": False, "error": f"Error leyendo CSV: {e}", "insertados": 0, "errores": 0}
    
    # Validar columnas requeridas
    required = ["codigo", "nombre", "fecha_ejecucion"]
    for col in required:
        if col not in df.columns:
            return {"exito": False, "error": f"Falta columna requerida: {col}", "insertados": 0, "errores": 0}
    
    insertados = 0
    errores = 0
    detalles = []
    
    for idx, row in df.iterrows():
        try:
            codigo = str(row["codigo"]).strip()
            nombre = str(row["nombre"]).strip()
            fecha = str(row["fecha_ejecucion"]).strip()
            hora = str(row["hora"]).strip() if "hora" in row and pd.notna(row["hora"]) else None
            ramo = str(row["ramo"]).strip() if "ramo" in row and pd.notna(row["ramo"]) else None
            estado = str(row["estado"]).strip() if "estado" in row and pd.notna(row["estado"]) else "pendiente"
            obs = str(row["observaciones"]).strip() if "observaciones" in row and pd.notna(row["observaciones"]) else ""
            
            # Validar fecha
            try:
                datetime.strptime(fecha, "%Y-%m-%d")
            except ValueError:
                errores += 1
                detalles.append(f"Fila {idx+2}: Formato de fecha inválido (use YYYY-MM-DD)")
                continue
            
            ok, msg = crear_proceso_masivo(codigo, nombre, fecha, hora, ramo, estado, obs)
            if ok:
                insertados += 1
            else:
                errores += 1
                detalles.append(f"Fila {idx+2}: {msg}")
        except Exception as e:
            errores += 1
            detalles.append(f"Fila {idx+2}: {e}")
    
    return {
        "exito": True,
        "insertados": insertados,
        "errores": errores,
        "detalles": detalles
    }


def get_plantilla_csv() -> str:
    """Retorna CSV de plantilla para descarga."""
    return """codigo,nombre,fecha_ejecucion,hora,ramo,estado,observaciones
17615,Reporte Mensual de Reserva Matemática F394,2026-10-15,08:00,087,pendiente,
17616,Reporte Mensual de Reserva Matemática F394,2026-10-15,08:00,088,pendiente,
17617,Reporte Mensual de Reserva Matemática F394,2026-10-15,08:00,093,pendiente,
17618,Carga SAP Cierre Contable,2026-10-20,10:00,,pendiente,
17619,Extracción Teradata,2026-10-10,06:00,,pendiente,"""


from datetime import timedelta