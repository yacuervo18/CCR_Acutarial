"""
Esquema de base de datos SQLite para CCR.
Todas las tablas usan borrado lógico (campo 'activo') salvo bitácoras y eventos_salida que son inmutables.
"""
from src.database.db_manager import get_connection


SCHEMA_SQL = """
-- ============================================================
-- USUARIOS / RESPONSABLES
-- ============================================================
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    email TEXT,
    activo INTEGER NOT NULL DEFAULT 1,
    creado_en TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- CONFIGURACIÓN GLOBAL (clave-valor)
-- ============================================================
CREATE TABLE IF NOT EXISTS configuracion (
    clave TEXT PRIMARY KEY,
    valor TEXT,
    descripcion TEXT,
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- CATÁLOGOS (datos semilla editables desde Configuración)
-- ============================================================
CREATE TABLE IF NOT EXISTS estados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    color TEXT NOT NULL,
    orden INTEGER NOT NULL DEFAULT 0,
    activo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS prioridades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    color TEXT NOT NULL,
    orden INTEGER NOT NULL DEFAULT 0,
    activo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tipos_evidencia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    extensiones_permitidas TEXT,  -- JSON array
    tamaño_max_mb INTEGER NOT NULL DEFAULT 10,
    activo INTEGER NOT NULL DEFAULT 1
);

-- ============================================================
-- PLANTILLAS DE PROCESOS (definición permanente)
-- ============================================================
CREATE TABLE IF NOT EXISTS procesos_plantilla (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    responsable_id INTEGER,
    prioridad_id INTEGER,
    dias_duracion_estimada INTEGER DEFAULT 1,
    orden INTEGER NOT NULL DEFAULT 0,
    activo INTEGER NOT NULL DEFAULT 1,
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (responsable_id) REFERENCES usuarios(id),
    FOREIGN KEY (prioridad_id) REFERENCES prioridades(id)
);

CREATE TABLE IF NOT EXISTS subtareas_plantilla (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proceso_plantilla_id INTEGER NOT NULL,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    orden INTEGER NOT NULL DEFAULT 0,
    activo INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (proceso_plantilla_id) REFERENCES procesos_plantilla(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS dependencias_plantilla (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proceso_plantilla_id INTEGER NOT NULL,      -- proceso que depende
    predecesora_id INTEGER NOT NULL,            -- proceso del que depende
    FOREIGN KEY (proceso_plantilla_id) REFERENCES procesos_plantilla(id) ON DELETE CASCADE,
    FOREIGN KEY (predecesora_id) REFERENCES procesos_plantilla(id) ON DELETE CASCADE,
    UNIQUE (proceso_plantilla_id, predecesora_id)
);

-- ============================================================
-- EJECUCIÓN MENSUAL (instancias por año/mes)
-- ============================================================
CREATE TABLE IF NOT EXISTS cierres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    año INTEGER NOT NULL,
    mes INTEGER NOT NULL,
    nombre TEXT,  -- ej. "Cierre Octubre 2026"
    estado TEXT NOT NULL DEFAULT 'Abierto',  -- Abierto, Cerrado
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    cerrado_en TEXT,
    UNIQUE (año, mes)
);

CREATE TABLE IF NOT EXISTS procesos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cierre_id INTEGER NOT NULL,
    proceso_plantilla_id INTEGER NOT NULL,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    responsable_id INTEGER,
    prioridad_id INTEGER,
    fecha_planeada TEXT,      -- ISO date
    fecha_limite TEXT,        -- ISO date
    estado_id INTEGER NOT NULL,
    observaciones TEXT,
    orden INTEGER NOT NULL DEFAULT 0,
    activo INTEGER NOT NULL DEFAULT 1,
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (cierre_id) REFERENCES cierres(id) ON DELETE CASCADE,
    FOREIGN KEY (proceso_plantilla_id) REFERENCES procesos_plantilla(id),
    FOREIGN KEY (responsable_id) REFERENCES usuarios(id),
    FOREIGN KEY (prioridad_id) REFERENCES prioridades(id),
    FOREIGN KEY (estado_id) REFERENCES estados(id)
);

CREATE TABLE IF NOT EXISTS subtareas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proceso_id INTEGER NOT NULL,
    subtarea_plantilla_id INTEGER,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    orden INTEGER NOT NULL DEFAULT 0,
    completada INTEGER NOT NULL DEFAULT 0,
    fecha_ejecucion TEXT,     -- ISO date
    observaciones TEXT,
    activo INTEGER NOT NULL DEFAULT 1,
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (proceso_id) REFERENCES procesos(id) ON DELETE CASCADE,
    FOREIGN KEY (subtarea_plantilla_id) REFERENCES subtareas_plantilla(id)
);

CREATE TABLE IF NOT EXISTS dependencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proceso_id INTEGER NOT NULL,
    predecesora_id INTEGER NOT NULL,
    FOREIGN KEY (proceso_id) REFERENCES procesos(id) ON DELETE CASCADE,
    FOREIGN KEY (predecesora_id) REFERENCES procesos(id) ON DELETE CASCADE,
    UNIQUE (proceso_id, predecesora_id)
);

-- ============================================================
-- PROCESOS MASIVOS
-- ============================================================
CREATE TABLE IF NOT EXISTS procesos_masivos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo TEXT NOT NULL,
    nombre TEXT NOT NULL,
    fecha_ejecucion TEXT NOT NULL,  -- ISO date
    hora TEXT,                      -- HH:MM
    ramo TEXT,
    estado_id INTEGER NOT NULL,
    observaciones TEXT,
    activo INTEGER NOT NULL DEFAULT 1,
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (estado_id) REFERENCES estados(id),
    UNIQUE (codigo, fecha_ejecucion, ramo)
);

-- ============================================================
-- CONTROLES SOX
-- ============================================================
CREATE TABLE IF NOT EXISTS controles_sox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cierre_id INTEGER NOT NULL,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    responsable_id INTEGER,
    fecha_ejecucion TEXT,     -- ISO date
    estado_id INTEGER NOT NULL,
    observaciones TEXT,
    orden INTEGER NOT NULL DEFAULT 0,
    activo INTEGER NOT NULL DEFAULT 1,
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (cierre_id) REFERENCES cierres(id) ON DELETE CASCADE,
    FOREIGN KEY (responsable_id) REFERENCES usuarios(id),
    FOREIGN KEY (estado_id) REFERENCES estados(id)
);

-- ============================================================
-- BITÁCORAS (inmutables)
-- ============================================================
CREATE TABLE IF NOT EXISTS bitacoras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL,           -- ISO datetime
    usuario TEXT NOT NULL,
    proceso_id INTEGER,
    subtarea_id INTEGER,
    control_sox_id INTEGER,
    aprobacion_id INTEGER,
    comentario TEXT NOT NULL,
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (proceso_id) REFERENCES procesos(id),
    FOREIGN KEY (subtarea_id) REFERENCES subtareas(id),
    FOREIGN KEY (control_sox_id) REFERENCES controles_sox(id),
    FOREIGN KEY (aprobacion_id) REFERENCES aprobaciones(id)
);

-- ============================================================
-- APROBACIONES
-- ============================================================
CREATE TABLE IF NOT EXISTS aprobaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cierre_id INTEGER NOT NULL,
    proceso_id INTEGER,
    nombre TEXT NOT NULL,
    estado_tecnico_id INTEGER NOT NULL,
    estado_aprobacion_id INTEGER NOT NULL,
    estado_sox_id INTEGER NOT NULL,
    responsable_id INTEGER,
    fecha_envio TEXT,           -- ISO date
    fecha_aprobacion TEXT,      -- ISO date
    observaciones TEXT,
    activo INTEGER NOT NULL DEFAULT 1,
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    actualizado_en TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (cierre_id) REFERENCES cierres(id) ON DELETE CASCADE,
    FOREIGN KEY (proceso_id) REFERENCES procesos(id),
    FOREIGN KEY (estado_tecnico_id) REFERENCES estados(id),
    FOREIGN KEY (estado_aprobacion_id) REFERENCES estados(id),
    FOREIGN KEY (estado_sox_id) REFERENCES estados(id),
    FOREIGN KEY (responsable_id) REFERENCES usuarios(id)
);

-- ============================================================
-- EVIDENCIAS
-- ============================================================
CREATE TABLE IF NOT EXISTS evidencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_evidencia_id INTEGER NOT NULL,
    entidad_tipo TEXT NOT NULL,  -- 'proceso', 'subtarea', 'control_sox', 'aprobacion'
    entidad_id INTEGER NOT NULL,
    nombre_archivo TEXT NOT NULL,
    nombre_original TEXT NOT NULL,
    ruta_relativa TEXT NOT NULL,  -- data/evidencias/{año}/{mes}/...
    tamaño_bytes INTEGER NOT NULL,
    mime_type TEXT,
    es_enlace INTEGER NOT NULL DEFAULT 0,
    enlace_url TEXT,
    descripcion TEXT,
    subido_por TEXT NOT NULL,
    subido_en TEXT NOT NULL DEFAULT (datetime('now')),
    activo INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (tipo_evidencia_id) REFERENCES tipos_evidencia(id)
);

-- ============================================================
-- BASE DE CONOCIMIENTO (enlaces)
-- ============================================================
CREATE TABLE IF NOT EXISTS conocimiento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proceso_plantilla_id INTEGER NOT NULL,
    tipo TEXT NOT NULL,  -- 'manual', 'teams', 'sharepoint', 'video', 'correo', 'ruta', 'otro'
    titulo TEXT NOT NULL,
    url TEXT NOT NULL,
    descripcion TEXT,
    activo INTEGER NOT NULL DEFAULT 1,
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (proceso_plantilla_id) REFERENCES procesos_plantilla(id) ON DELETE CASCADE
);

-- ============================================================
-- ALERTAS Y EVENTOS DE SALIDA (para Teams)
-- ============================================================
CREATE TABLE IF NOT EXISTS alertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,  -- 'fecha_proxima', 'vencido', 'sox_pendiente', 'aprobacion_pendiente', 'bloqueado', 'masivo_proximo'
    severidad TEXT NOT NULL,  -- 'Info', 'Aviso', 'Critica'
    titulo TEXT NOT NULL,
    mensaje TEXT NOT NULL,
    proceso_id INTEGER,
    subtarea_id INTEGER,
    control_sox_id INTEGER,
    aprobacion_id INTEGER,
    proceso_masivo_id INTEGER,
    cierre_id INTEGER,
    responsable_id INTEGER,
    fecha_limite TEXT,        -- ISO date
    leida INTEGER NOT NULL DEFAULT 0,
    pospuesta_hasta TEXT,     -- ISO datetime
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (proceso_id) REFERENCES procesos(id),
    FOREIGN KEY (subtarea_id) REFERENCES subtareas(id),
    FOREIGN KEY (control_sox_id) REFERENCES controles_sox(id),
    FOREIGN KEY (aprobacion_id) REFERENCES aprobaciones(id),
    FOREIGN KEY (proceso_masivo_id) REFERENCES procesos_masivos(id),
    FOREIGN KEY (cierre_id) REFERENCES cierres(id),
    FOREIGN KEY (responsable_id) REFERENCES usuarios(id)
);

CREATE TABLE IF NOT EXISTS eventos_salida (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_alerta TEXT NOT NULL,
    severidad TEXT NOT NULL,  -- 'Info', 'Aviso', 'Critica'
    clave_unica TEXT NOT NULL UNIQUE,  -- hash para deduplicación
    payload_json TEXT NOT NULL,
    canal TEXT NOT NULL DEFAULT 'teams',
    estado TEXT NOT NULL DEFAULT 'Pendiente',  -- 'Pendiente', 'Enviado', 'Error', 'Omitido'
    intentos INTEGER NOT NULL DEFAULT 0,
    ultimo_error TEXT,
    creado_en TEXT NOT NULL DEFAULT (datetime('now')),
    enviado_en TEXT
);

-- ============================================================
-- ÍNDICES PARA RENDIMIENTO
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_procesos_cierre ON procesos(cierre_id);
CREATE INDEX IF NOT EXISTS idx_procesos_estado ON procesos(estado_id);
CREATE INDEX IF NOT EXISTS idx_procesos_responsable ON procesos(responsable_id);
CREATE INDEX IF NOT EXISTS idx_subtareas_proceso ON subtareas(proceso_id);
CREATE INDEX IF NOT EXISTS idx_dependencias_proceso ON dependencias(proceso_id);
CREATE INDEX IF NOT EXISTS idx_bitacoras_fecha ON bitacoras(fecha);
CREATE INDEX IF NOT EXISTS idx_bitacoras_proceso ON bitacoras(proceso_id);
CREATE INDEX IF NOT EXISTS idx_alertas_cierre ON alertas(cierre_id);
CREATE INDEX IF NOT EXISTS idx_alertas_leida ON alertas(leida);
CREATE INDEX IF NOT EXISTS idx_eventos_salida_estado ON eventos_salida(estado);
CREATE INDEX IF NOT EXISTS idx_eventos_salida_clave ON eventos_salida(clave_unica);
CREATE INDEX IF NOT EXISTS idx_procesos_masivos_fecha ON procesos_masivos(fecha_ejecucion);
CREATE INDEX IF NOT EXISTS idx_controles_sox_cierre ON controles_sox(cierre_id);
CREATE INDEX IF NOT EXISTS idx_aprobaciones_cierre ON aprobaciones(cierre_id);
CREATE INDEX IF NOT EXISTS idx_evidencias_entidad ON evidencias(entidad_tipo, entidad_id);
"""


def init_schema():
    """Crea todas las tablas e índices."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_schema()
    print("Esquema creado correctamente.")