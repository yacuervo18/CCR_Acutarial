"""
Servicio de configuración - Clave/valor global.
"""
from src.database.db_manager import execute_query, execute_one, execute_insert, execute_update


def get_config(clave: str, default: str = "") -> str:
    """Obtiene un valor de configuración."""
    row = execute_one("SELECT valor FROM configuracion WHERE clave = ?", (clave,))
    return row["valor"] if row and row["valor"] is not None else default


def set_config(clave: str, valor: str, descripcion: str = "") -> bool:
    """Establece un valor de configuración."""
    exists = execute_one("SELECT 1 FROM configuracion WHERE clave = ?", (clave,))
    if exists:
        return execute_update(
            "UPDATE configuracion SET valor = ?, descripcion = ?, actualizado_en = datetime('now') WHERE clave = ?",
            (valor, descripcion, clave)
        ) > 0
    else:
        return execute_insert(
            "INSERT INTO configuracion (clave, valor, descripcion) VALUES (?, ?, ?)",
            (clave, valor, descripcion)
        ) > 0


def get_all_config() -> dict:
    """Obtiene toda la configuración como diccionario."""
    rows = execute_query("SELECT clave, valor, descripcion FROM configuracion")
    return {row["clave"]: {"valor": row["valor"], "descripcion": row["descripcion"]} for row in rows}


def get_usuarios_activos() -> list[dict]:
    rows = execute_query("SELECT id, nombre, email FROM usuarios WHERE activo = 1 ORDER BY nombre")
    return [dict(row) for row in rows]


def get_estados_activos() -> list[dict]:
    rows = execute_query("SELECT id, codigo, nombre, color FROM estados WHERE activo = 1 ORDER BY orden")
    return [dict(row) for row in rows]


def get_prioridades_activas() -> list[dict]:
    rows = execute_query("SELECT id, codigo, nombre, color FROM prioridades WHERE activo = 1 ORDER BY orden")
    return [dict(row) for row in rows]


def get_tipos_evidencia_activos() -> list[dict]:
    rows = execute_query("SELECT * FROM tipos_evidencia WHERE activo = 1 ORDER BY nombre")
    return [dict(row) for row in rows]