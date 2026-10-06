"""
Migraciones de esquema - Versionado con user_version.
"""
from src.database.db_manager import get_db_version, set_db_version, execute_script


MIGRATIONS = {
    1: """
        -- Versión 1: Esquema inicial completo
        -- Se aplica via schema.py
    """,
    2: """
        -- Versión 2: Agregar campo clave_unica a alertas
        ALTER TABLE alertas ADD COLUMN clave_unica TEXT;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_alertas_clave ON alertas(clave_unica);
    """,
    3: """
        -- Versión 3: Agregar tabla eventos_salida
        CREATE TABLE IF NOT EXISTS eventos_salida (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_alerta TEXT NOT NULL,
            severidad TEXT NOT NULL,
            clave_unica TEXT NOT NULL UNIQUE,
            payload_json TEXT NOT NULL,
            canal TEXT NOT NULL DEFAULT 'teams',
            estado TEXT NOT NULL DEFAULT 'Pendiente',
            intentos INTEGER NOT NULL DEFAULT 0,
            ultimo_error TEXT,
            creado_en TEXT NOT NULL DEFAULT (datetime('now')),
            enviado_en TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_eventos_salida_estado ON eventos_salida(estado);
        CREATE INDEX IF NOT EXISTS idx_eventos_salida_clave ON eventos_salida(clave_unica);
    """,
}


def run_migrations():
    """Ejecuta migraciones pendientes."""
    current_version = get_db_version()
    target_version = max(MIGRATIONS.keys())
    
    if current_version >= target_version:
        return
    
    print(f"Ejecutando migraciones: v{current_version} -> v{target_version}")
    
    for version in range(current_version + 1, target_version + 1):
        if version in MIGRATIONS:
            print(f"  Aplicando v{version}...")
            execute_script(MIGRATIONS[version])
            set_db_version(version)
    
    print("Migraciones completadas.")


def get_current_version() -> int:
    return get_db_version()