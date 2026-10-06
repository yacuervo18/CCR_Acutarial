"""
Queries SQL centralizadas - Todas las consultas parametrizadas.
"""
from src.database.db_manager import execute_query, execute_one


# ============================================================
# CIERRES
# ============================================================
def get_cierre_actual():
    from datetime import date
    hoy = date.today()
    return execute_one("SELECT * FROM cierres WHERE año = ? AND mes = ?", (hoy.year, hoy.month))


def get_cierres_historial(limite: int = 24):
    return execute_query("SELECT * FROM cierres ORDER BY año DESC, mes DESC LIMIT ?", (limite,))


# ============================================================
# PROCESOS
# ============================================================
def get_procesos_cierre(cierre_id: int):
    return execute_query("""
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


def get_proceso_detalle(proceso_id: int):
    return execute_one("""
        SELECT p.*, e.codigo as estado_codigo, e.nombre as estado_nombre, e.color as estado_color,
               pr.codigo as prioridad_codigo, pr.nombre as prioridad_nombre, pr.color as prioridad_color,
               u.nombre as responsable_nombre, u.email as responsable_email
        FROM procesos p
        LEFT JOIN estados e ON p.estado_id = e.id
        LEFT JOIN prioridades pr ON p.prioridad_id = pr.id
        LEFT JOIN usuarios u ON p.responsable_id = u.id
        WHERE p.id = ? AND p.activo = 1
    """, (proceso_id,))


def get_dependencias_proceso(proceso_id: int):
    return execute_query("""
        SELECT d.*, p.nombre as predecesora_nombre, e.codigo as predecesora_estado_codigo
        FROM dependencias d
        JOIN procesos p ON d.predecesora_id = p.id
        JOIN estados e ON p.estado_id = e.id
        WHERE d.proceso_id = ?
    """, (proceso_id,))


# ============================================================
# SUBTAREAS
# ============================================================
def get_subtareas_proceso(proceso_id: int):
    return execute_query("""
        SELECT s.*, sp.nombre as plantilla_nombre
        FROM subtareas s
        LEFT JOIN subtareas_plantilla sp ON s.subtarea_plantilla_id = sp.id
        WHERE s.proceso_id = ? AND s.activo = 1
        ORDER BY s.orden
    """, (proceso_id,))


# ============================================================
# PLANTILLAS
# ============================================================
def get_procesos_plantilla():
    return execute_query("""
        SELECT pp.*, pr.codigo as prioridad_codigo, pr.nombre as prioridad_nombre
        FROM procesos_plantilla pp
        LEFT JOIN prioridades pr ON pp.prioridad_id = pr.id
        WHERE pp.activo = 1
        ORDER BY pp.orden
    """)


def get_subtareas_plantilla(proceso_plantilla_id: int):
    return execute_query("""
        SELECT * FROM subtareas_plantilla
        WHERE proceso_plantilla_id = ? AND activo = 1
        ORDER BY orden
    """, (proceso_plantilla_id,))


def get_dependencias_plantilla(proceso_plantilla_id: int):
    return execute_query("""
        SELECT dp.*, pp.nombre as predecesora_nombre
        FROM dependencias_plantilla dp
        JOIN procesos_plantilla pp ON dp.predecesora_id = pp.id
        WHERE dp.proceso_plantilla_id = ?
    """, (proceso_plantilla_id,))


# ============================================================
# CATÁLOGOS
# ============================================================
def get_estados_activos():
    return execute_query("SELECT * FROM estados WHERE activo = 1 ORDER BY orden")


def get_prioridades_activas():
    return execute_query("SELECT * FROM prioridades WHERE activo = 1 ORDER BY orden")


def get_tipos_evidencia_activos():
    return execute_query("SELECT * FROM tipos_evidencia WHERE activo = 1 ORDER BY nombre")


def get_usuarios_activos():
    return execute_query("SELECT id, nombre, email FROM usuarios WHERE activo = 1 ORDER BY nombre")


# ============================================================
# PROCESOS MASIVOS
# ============================================================
def get_procesos_masivos(filtros: dict = None):
    conditions = ["activo = 1"]
    params = []
    
    if filtros:
        if filtros.get("fecha_desde"):
            conditions.append("fecha_ejecucion >= ?")
            params.append(filtros["fecha_desde"])
        if filtros.get("fecha_hasta"):
            conditions.append("fecha_ejecucion <= ?")
            params.append(filtros["fecha_hasta"])
        if filtros.get("estado_codigo"):
            conditions.append("estado_id = (SELECT id FROM estados WHERE codigo = ?)")
            params.append(filtros["estado_codigo"])
        if filtros.get("ramo"):
            conditions.append("ramo = ?")
            params.append(filtros["ramo"])
    
    where = "WHERE " + " AND ".join(conditions)
    
    return execute_query(f"""
        SELECT pm.*, e.codigo as estado_codigo, e.nombre as estado_nombre, e.color as estado_color
        FROM procesos_masivos pm
        JOIN estados e ON pm.estado_id = e.id
        {where}
        ORDER BY pm.fecha_ejecucion, pm.hora
    """, tuple(params))


# ============================================================
# CONTROLES SOX
# ============================================================
def get_controles_sox_cierre(cierre_id: int):
    return execute_query("""
        SELECT cs.*, e.codigo as estado_codigo, e.nombre as estado_nombre, e.color as estado_color,
               u.nombre as responsable_nombre
        FROM controles_sox cs
        JOIN estados e ON cs.estado_id = e.id
        LEFT JOIN usuarios u ON cs.responsable_id = u.id
        WHERE cs.cierre_id = ? AND cs.activo = 1
        ORDER BY cs.orden
    """, (cierre_id,))


# ============================================================
# APROBACIONES
# ============================================================
def get_aprobaciones_cierre(cierre_id: int):
    return execute_query("""
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


# ============================================================
# BITÁCORAS
# ============================================================
def get_bitacoras_proceso(proceso_id: int):
    return execute_query("""
        SELECT * FROM bitacoras
        WHERE proceso_id = ?
        ORDER BY fecha DESC
    """, (proceso_id,))


def get_bitacoras_global(filtros: dict = None, limite: int = 100):
    conditions = []
    params = []
    
    if filtros:
        if filtros.get("fecha_desde"):
            conditions.append("fecha >= ?")
            params.append(filtros["fecha_desde"])
        if filtros.get("fecha_hasta"):
            conditions.append("fecha <= ?")
            params.append(filtros["fecha_hasta"])
        if filtros.get("proceso_id"):
            conditions.append("proceso_id = ?")
            params.append(filtros["proceso_id"])
        if filtros.get("usuario"):
            conditions.append("usuario = ?")
            params.append(filtros["usuario"])
    
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    params.append(limite)
    
    return execute_query(f"""
        SELECT b.*, p.nombre as proceso_nombre
        FROM bitacoras b
        LEFT JOIN procesos p ON b.proceso_id = p.id
        {where}
        ORDER BY b.fecha DESC
        LIMIT ?
    """, tuple(params))


# ============================================================
# EVIDENCIAS
# ============================================================
def get_evidencias_entidad(entidad_tipo: str, entidad_id: int):
    return execute_query("""
        SELECT e.*, te.codigo as tipo_codigo, te.nombre as tipo_nombre
        FROM evidencias e
        JOIN tipos_evidencia te ON e.tipo_evidencia_id = te.id
        WHERE e.entidad_tipo = ? AND e.entidad_id = ? AND e.activo = 1
        ORDER BY e.subido_en DESC
    """, (entidad_tipo, entidad_id))


def get_evidencias_filtros(filtros: dict = None):
    conditions = ["e.activo = 1"]
    params = []
    
    if filtros:
        if filtros.get("tipo_evidencia_id"):
            conditions.append("e.tipo_evidencia_id = ?")
            params.append(filtros["tipo_evidencia_id"])
        if filtros.get("entidad_tipo"):
            conditions.append("e.entidad_tipo = ?")
            params.append(filtros["entidad_tipo"])
        if filtros.get("año"):
            conditions.append("strftime('%Y', e.subido_en) = ?")
            params.append(str(filtros["año"]))
        if filtros.get("mes"):
            conditions.append("strftime('%m', e.subido_en) = ?")
            params.append(f"{filtros['mes']:02d}")
    
    where = "WHERE " + " AND ".join(conditions)
    
    return execute_query(f"""
        SELECT e.*, te.codigo as tipo_codigo, te.nombre as tipo_nombre
        FROM evidencias e
        JOIN tipos_evidencia te ON e.tipo_evidencia_id = te.id
        {where}
        ORDER BY e.subido_en DESC
    """, tuple(params))


# ============================================================
# CONOCIMIENTO
# ============================================================
def get_conocimiento_proceso(proceso_plantilla_id: int):
    return execute_query("""
        SELECT * FROM conocimiento
        WHERE proceso_plantilla_id = ? AND activo = 1
        ORDER BY tipo, titulo
    """, (proceso_plantilla_id,))


# ============================================================
# ALERTAS
# ============================================================
def get_alertas_cierre(cierre_id: int, solo_no_leidas: bool = False):
    where = "WHERE cierre_id = ?"
    params = [cierre_id]
    if solo_no_leidas:
        where += " AND leida = 0"
    
    return execute_query(f"""
        SELECT a.*, u.nombre as responsable_nombre, u.email as responsable_email
        FROM alertas a
        LEFT JOIN usuarios u ON a.responsable_id = u.id
        {where}
        ORDER BY 
            CASE a.severidad WHEN 'Critica' THEN 1 WHEN 'Aviso' THEN 2 ELSE 3 END,
            a.creado_en DESC
    """, tuple(params))


def get_alertas_activas_toast(cierre_id: int):
    return execute_query("""
        SELECT * FROM alertas
        WHERE cierre_id = ? AND leida = 0
        AND (pospuesta_hasta IS NULL OR pospuesta_hasta <= datetime('now'))
        AND severidad IN ('Critica', 'Aviso')
        ORDER BY 
            CASE severidad WHEN 'Critica' THEN 1 ELSE 2 END,
            creado_en DESC
        LIMIT 5
    """, (cierre_id,))


# ============================================================
# EVENTOS SALIDA
# ============================================================
def get_eventos_pendientes(limite: int = 50):
    return execute_query("""
        SELECT * FROM eventos_salida
        WHERE estado IN ('Pendiente', 'Error')
        ORDER BY creado_en
        LIMIT ?
    """, (limite,))


def get_evento_by_clave(clave_unica: str):
    return execute_one("SELECT * FROM eventos_salida WHERE clave_unica = ?", (clave_unica,))


# ============================================================
# CONFIGURACIÓN
# ============================================================
def get_config(clave: str):
    return execute_one("SELECT valor FROM configuracion WHERE clave = ?", (clave,))


def get_all_config():
    return execute_query("SELECT clave, valor, descripcion FROM configuracion")