"""
Servicios de procesos - Lógica de negocio para procesos, subtareas y dependencias.
"""
from datetime import date, datetime, timedelta
from typing import Optional
from src.database.db_manager import (
    get_connection, execute_query, execute_one, execute_insert, execute_update, transaction
)
from src.models import Proceso, Subtarea, Cierre, Estado, Prioridad


def get_cierre_actual() -> Optional[Cierre]:
    """Obtiene el cierre del mes actual."""
    hoy = date.today()
    row = execute_one(
        "SELECT * FROM cierres WHERE año = ? AND mes = ?", (hoy.year, hoy.month)
    )
    if row:
        return Cierre(
            id=row["id"],
            año=row["año"],
            mes=row["mes"],
            nombre=row["nombre"],
            estado=row["estado"],
            creado_en=datetime.fromisoformat(row["creado_en"]) if row["creado_en"] else None,
            cerrado_en=datetime.fromisoformat(row["cerrado_en"]) if row["cerrado_en"] else None
        )
    return None


def get_cierre_by_id(cierre_id: int) -> Optional[Cierre]:
    row = execute_one("SELECT * FROM cierres WHERE id = ?", (cierre_id,))
    if row:
        return Cierre(
            id=row["id"],
            año=row["año"],
            mes=row["mes"],
            nombre=row["nombre"],
            estado=row["estado"],
            creado_en=datetime.fromisoformat(row["creado_en"]) if row["creado_en"] else None,
            cerrado_en=datetime.fromisoformat(row["cerrado_en"]) if row["cerrado_en"] else None
        )
    return None


def get_procesos_cierre(cierre_id: int) -> list[dict]:
    """Obtiene todos los procesos de un cierre con info enriquecida."""
    rows = execute_query("""
        SELECT p.*, e.codigo as estado_codigo, e.nombre as estado_nombre, e.color as estado_color,
               pr.codigo as prioridad_codigo, pr.nombre as prioridad_nombre, pr.color as prioridad_color,
               u.nombre as responsable_nombre,
               (SELECT COUNT(*) FROM subtareas WHERE proceso_id = p.id AND activo = 1) as total_subtareas,
               (SELECT COUNT(*) FROM subtareas WHERE proceso_id = p.id AND activo = 1 AND completada = 1) as subtareas_completadas
        FROM procesos p
        LEFT JOIN estados e ON p.estado_id = e.id
        LEFT JOIN prioridades pr ON p.prioridad_id = pr.id
        LEFT JOIN usuarios u ON p.responsable_id = u.id
        WHERE p.cierre_id = ? AND p.activo = 1
        ORDER BY p.orden
    """, (cierre_id,))
    
    procesos = []
    for row in rows:
        # Verificar si está bloqueado por dependencias
        bloqueado, motivo = verificar_bloqueado_por_dependencias(row["id"])
        
        procesos.append({
            "id": row["id"],
            "nombre": row["nombre"],
            "descripcion": row["descripcion"],
            "responsable_id": row["responsable_id"],
            "responsable_nombre": row["responsable_nombre"],
            "prioridad_id": row["prioridad_id"],
            "prioridad_codigo": row["prioridad_codigo"],
            "prioridad_nombre": row["prioridad_nombre"],
            "prioridad_color": row["prioridad_color"],
            "fecha_planeada": row["fecha_planeada"],
            "fecha_limite": row["fecha_limite"],
            "estado_id": row["estado_id"],
            "estado_codigo": row["estado_codigo"],
            "estado_nombre": row["estado_nombre"],
            "estado_color": row["estado_color"],
            "observaciones": row["observaciones"],
            "orden": row["orden"],
            "total_subtareas": row["total_subtareas"],
            "subtareas_completadas": row["subtareas_completadas"],
            "bloqueado": bloqueado,
            "motivo_bloqueo": motivo
        })
    return procesos


def get_proceso_by_id(proceso_id: int) -> Optional[dict]:
    row = execute_one("""
        SELECT p.*, e.codigo as estado_codigo, e.nombre as estado_nombre, e.color as estado_color,
               pr.codigo as prioridad_codigo, pr.nombre as prioridad_nombre, pr.color as prioridad_color,
               u.nombre as responsable_nombre, u.email as responsable_email
        FROM procesos p
        LEFT JOIN estados e ON p.estado_id = e.id
        LEFT JOIN prioridades pr ON p.prioridad_id = pr.id
        LEFT JOIN usuarios u ON p.responsable_id = u.id
        WHERE p.id = ? AND p.activo = 1
    """, (proceso_id,))
    
    if not row:
        return None
    
    bloqueado, motivo = verificar_bloqueado_por_dependencias(proceso_id)
    
    return {
        "id": row["id"],
        "cierre_id": row["cierre_id"],
        "proceso_plantilla_id": row["proceso_plantilla_id"],
        "nombre": row["nombre"],
        "descripcion": row["descripcion"],
        "responsable_id": row["responsable_id"],
        "responsable_nombre": row["responsable_nombre"],
        "responsable_email": row["responsable_email"],
        "prioridad_id": row["prioridad_id"],
        "prioridad_codigo": row["prioridad_codigo"],
        "prioridad_nombre": row["prioridad_nombre"],
        "prioridad_color": row["prioridad_color"],
        "fecha_planeada": row["fecha_planeada"],
        "fecha_limite": row["fecha_limite"],
        "estado_id": row["estado_id"],
        "estado_codigo": row["estado_codigo"],
        "estado_nombre": row["estado_nombre"],
        "estado_color": row["estado_color"],
        "observaciones": row["observaciones"],
        "orden": row["orden"],
        "bloqueado": bloqueado,
        "motivo_bloqueo": motivo
    }


def get_subtareas_proceso(proceso_id: int) -> list[dict]:
    rows = execute_query("""
        SELECT s.*, sp.nombre as plantilla_nombre
        FROM subtareas s
        LEFT JOIN subtareas_plantilla sp ON s.subtarea_plantilla_id = sp.id
        WHERE s.proceso_id = ? AND s.activo = 1
        ORDER BY s.orden
    """, (proceso_id,))
    
    return [dict(row) for row in rows]


def get_dependencias_proceso(proceso_id: int) -> list[dict]:
    """Obtiene las dependencias (predecesoras) de un proceso."""
    rows = execute_query("""
        SELECT d.*, p.nombre as predecesora_nombre, e.codigo as predecesora_estado_codigo
        FROM dependencias d
        JOIN procesos p ON d.predecesora_id = p.id
        JOIN estados e ON p.estado_id = e.id
        WHERE d.proceso_id = ?
    """, (proceso_id,))
    
    return [dict(row) for row in rows]


def verificar_bloqueado_por_dependencias(proceso_id: int) -> tuple[bool, str]:
    """
    Verifica si un proceso está bloqueado por dependencias no completadas.
    Retorna (bloqueado, motivo).
    """
    deps = get_dependencias_proceso(proceso_id)
    pendientes = [d for d in deps if d["predecesora_estado_codigo"] != "completado"]
    
    if pendientes:
        nombres = ", ".join([d["predecesora_nombre"] for d in pendientes])
        return True, f"Dependencia pendiente: {nombres}"
    return False, ""


def actualizar_estados_bloqueados(cierre_id: int):
    """Actualiza automáticamente el estado 'Bloqueado' basado en dependencias."""
    procesos = get_procesos_cierre(cierre_id)
    
    estado_bloqueado_id = execute_one("SELECT id FROM estados WHERE codigo = 'bloqueado'")["id"]
    estado_pendiente_id = execute_one("SELECT id FROM estados WHERE codigo = 'pendiente'")["id"]
    estado_en_proceso_id = execute_one("SELECT id FROM estados WHERE codigo = 'en_proceso'")["id"]
    
    for proc in procesos:
        bloqueado, motivo = verificar_bloqueado_por_dependencias(proc["id"])
        estado_actual = proc["estado_codigo"]
        
        if bloqueado and estado_actual not in ("bloqueado", "completado", "cancelado"):
            execute_update(
                "UPDATE procesos SET estado_id = ?, actualizado_en = datetime('now') WHERE id = ?",
                (estado_bloqueado_id, proc["id"])
            )
            registrar_bitacora_proceso(proc["id"], None, f"Estado cambiado a Bloqueado automáticamente: {motivo}")
        elif not bloqueado and estado_actual == "bloqueado":
            # Volver a pendiente o en_proceso según corresponda
            nuevo_estado = estado_en_proceso_id if proc["subtareas_completadas"] > 0 else estado_pendiente_id
            execute_update(
                "UPDATE procesos SET estado_id = ?, actualizado_en = datetime('now') WHERE id = ?",
                (nuevo_estado, proc["id"])
            )
            registrar_bitacora_proceso(proc["id"], None, "Estado desbloqueado automáticamente")


def get_estados() -> list[Estado]:
    rows = execute_query("SELECT * FROM estados WHERE activo = 1 ORDER BY orden")
    return [Estado(
        id=r["id"], codigo=r["codigo"], nombre=r["nombre"],
        color=r["color"], orden=r["orden"], activo=bool(r["activo"])
    ) for r in rows]


def get_prioridades() -> list[Prioridad]:
    rows = execute_query("SELECT * FROM prioridades WHERE activo = 1 ORDER BY orden")
    return [Prioridad(
        id=r["id"], codigo=r["codigo"], nombre=r["nombre"],
        color=r["color"], orden=r["orden"], activo=bool(r["activo"])
    ) for r in rows]


def get_estado_by_codigo(codigo: str) -> Optional[Estado]:
    row = execute_one("SELECT * FROM estados WHERE codigo = ?", (codigo,))
    if row:
        return Estado(
            id=row["id"], codigo=row["codigo"], nombre=row["nombre"],
            color=row["color"], orden=row["orden"], activo=bool(row["activo"])
        )
    return None


def calcular_avance_cierre(cierre_id: int) -> dict:
    """Calcula el avance del cierre mensual."""
    procesos = get_procesos_cierre(cierre_id)
    
    # Filtrar procesos no cancelados
    activos = [p for p in procesos if p["estado_codigo"] != "cancelado"]
    total = len(activos)
    completados = len([p for p in activos if p["estado_codigo"] == "completado"])
    en_proceso = len([p for p in activos if p["estado_codigo"] == "en_proceso"])
    vencidos = len([p for p in activos if p["estado_codigo"] == "vencido"])
    bloqueados = len([p for p in activos if p["estado_codigo"] == "bloqueado"])
    pendientes = len([p for p in activos if p["estado_codigo"] == "pendiente"])
    pendientes_aprob = len([p for p in activos if p["estado_codigo"] == "pendiente_aprobacion"])
    
    porcentaje = round((completados / total * 100) if total > 0 else 0)
    
    return {
        "total": total,
        "completados": completados,
        "en_proceso": en_proceso,
        "vencidos": vencidos,
        "bloqueados": bloqueados,
        "pendientes": pendientes,
        "pendientes_aprobacion": pendientes_aprob,
        "porcentaje": porcentaje,
        "porcentajes_barra": {
            "verde": round(completados / total * 100) if total > 0 else 0,
            "ambar": round(en_proceso / total * 100) if total > 0 else 0,
            "rojo": round(vencidos / total * 100) if total > 0 else 0,
            "gris": round(bloqueados / total * 100) if total > 0 else 0,
        }
    }


def get_procesos_vencidos(cierre_id: int) -> list[dict]:
    """Procesos vencidos (fecha_limite pasada y no completados)."""
    hoy = date.today().isoformat()
    rows = execute_query("""
        SELECT p.*, e.codigo as estado_codigo
        FROM procesos p
        JOIN estados e ON p.estado_id = e.id
        WHERE p.cierre_id = ? AND p.activo = 1
        AND p.fecha_limite IS NOT NULL AND p.fecha_limite < ?
        AND e.codigo NOT IN ('completado', 'cancelado')
        ORDER BY p.fecha_limite
    """, (cierre_id, hoy))
    return [dict(row) for row in rows]


def get_procesos_bloqueados(cierre_id: int) -> list[dict]:
    procesos = get_procesos_cierre(cierre_id)
    return [p for p in procesos if p["bloqueado"]]


def get_procesos_criticos(cierre_id: int) -> list[dict]:
    """Procesos con prioridad crítica y no completados."""
    rows = execute_query("""
        SELECT p.*, e.codigo as estado_codigo, pr.codigo as prioridad_codigo
        FROM procesos p
        JOIN estados e ON p.estado_id = e.id
        JOIN prioridades pr ON p.prioridad_id = pr.id
        WHERE p.cierre_id = ? AND p.activo = 1
        AND pr.codigo = 'critica'
        AND e.codigo NOT IN ('completado', 'cancelado')
        ORDER BY p.orden
    """, (cierre_id,))
    return [dict(row) for row in rows]


def get_tareas_pendientes_hoy(cierre_id: int) -> list[dict]:
    """Subtareas pendientes para hoy."""
    hoy = date.today().isoformat()
    rows = execute_query("""
        SELECT s.*, p.nombre as proceso_nombre
        FROM subtareas s
        JOIN procesos p ON s.proceso_id = p.id
        WHERE p.cierre_id = ? AND s.activo = 1
        AND s.completada = 0
        AND (s.fecha_ejecucion IS NULL OR s.fecha_ejecucion <= ?)
        ORDER BY p.orden, s.orden
        LIMIT 10
    """, (cierre_id, hoy))
    return [dict(row) for row in rows]


def get_proximos_vencimientos(cierre_id: int, dias: int = 7) -> list[dict]:
    """Procesos con fecha límite en los próximos días."""
    hoy = date.today()
    limite = (hoy + timedelta(days=dias)).isoformat()
    hoy_iso = hoy.isoformat()
    
    rows = execute_query("""
        SELECT p.*, e.codigo as estado_codigo
        FROM procesos p
        JOIN estados e ON p.estado_id = e.id
        WHERE p.cierre_id = ? AND p.activo = 1
        AND p.fecha_limite IS NOT NULL
        AND p.fecha_limite BETWEEN ? AND ?
        AND e.codigo NOT IN ('completado', 'cancelado')
        ORDER BY p.fecha_limite
        LIMIT 10
    """, (cierre_id, hoy_iso, limite))
    return [dict(row) for row in rows]


def registrar_bitacora_proceso(proceso_id: int, subtarea_id: Optional[int], comentario: str):
    """Registra una entrada en bitácora para un proceso."""
    from src.services.bitacoras_service import registrar_bitacora
    # Obtener usuario actual de configuración
    from src.services.config_service import get_config
    usuario = get_config("usuario_actual", "Usuario Actual")
    registrar_bitacora(usuario, proceso_id, subtarea_id, None, None, comentario)


def actualizar_proceso(proceso_id: int, **kwargs) -> bool:
    """Actualiza campos de un proceso."""
    campos_permitidos = [
        "nombre", "descripcion", "responsable_id", "prioridad_id",
        "fecha_planeada", "fecha_limite", "estado_id", "observaciones", "orden"
    ]
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in campos_permitidos and v is not None:
            updates.append(f"{k} = ?")
            params.append(v)
    
    if not updates:
        return False
    
    updates.append("actualizado_en = datetime('now')")
    params.append(proceso_id)
    
    query = f"UPDATE procesos SET {', '.join(updates)} WHERE id = ?"
    return execute_update(query, tuple(params)) > 0


def actualizar_subtarea(subtarea_id: int, **kwargs) -> bool:
    """Actualiza campos de una subtarea."""
    campos_permitidos = ["nombre", "descripcion", "orden", "completada", "fecha_ejecucion", "observaciones"]
    updates = []
    params = []
    for k, v in kwargs.items():
        if k in campos_permitidos and v is not None:
            updates.append(f"{k} = ?")
            params.append(v)
    
    if not updates:
        return False
    
    updates.append("actualizado_en = datetime('now')")
    params.append(subtarea_id)
    
    query = f"UPDATE subtareas SET {', '.join(updates)} WHERE id = ?"
    return execute_update(query, tuple(params)) > 0


def completar_subtarea(subtarea_id: int, observaciones: str = "") -> bool:
    """Marca una subtarea como completada."""
    hoy = date.today().isoformat()
    with transaction() as conn:
        conn.execute(
            "UPDATE subtareas SET completada = 1, fecha_ejecucion = ?, observaciones = ?, actualizado_en = datetime('now') WHERE id = ?",
            (hoy, observaciones, subtarea_id)
        )
        # Registrar en bitácora
        row = conn.execute("SELECT proceso_id FROM subtareas WHERE id = ?", (subtarea_id,)).fetchone()
        if row:
            conn.execute(
                "INSERT INTO bitacoras (fecha, usuario, proceso_id, subtarea_id, comentario) VALUES (datetime('now'), ?, ?, ?, ?)",
                ("Usuario Actual", row["proceso_id"], subtarea_id, f"Subtarea completada: {observaciones}")
            )
    return True


def detectar_ciclo_dependencias(proceso_id: int, nueva_predecesora_id: int) -> bool:
    """
    Detecta si agregar una dependencia crearía un ciclo.
    Usa DFS para detectar ciclos en el grafo de dependencias.
    """
    if proceso_id == nueva_predecesora_id:
        return True
    
    visited = set()
    stack = [nueva_predecesora_id]
    
    while stack:
        current = stack.pop()
        if current == proceso_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        
        # Obtener predecesoras de current
        rows = execute_query(
            "SELECT predecesora_id FROM dependencias WHERE proceso_id = ?", (current,)
        )
        for row in rows:
            stack.append(row["predecesora_id"])
    
    return False


def agregar_dependencia(proceso_id: int, predecesora_id: int) -> tuple[bool, str]:
    """Agrega una dependencia validando ciclos."""
    if detectar_ciclo_dependencias(proceso_id, predecesora_id):
        return False, "Esta dependencia crearía un ciclo en el flujo de procesos."
    
    try:
        execute_insert(
            "INSERT INTO dependencias (proceso_id, predecesora_id) VALUES (?, ?)",
            (proceso_id, predecesora_id)
        )
        # Actualizar estados bloqueados
        row = execute_one("SELECT cierre_id FROM procesos WHERE id = ?", (proceso_id,))
        if row:
            actualizar_estados_bloqueados(row["cierre_id"])
        return True, "Dependencia agregada."
    except sqlite3.IntegrityError:
        return False, "La dependencia ya existe."


import sqlite3