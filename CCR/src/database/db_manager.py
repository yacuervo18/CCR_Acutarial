"""
Gestor de conexión a base de datos SQLite.
Maneja transacciones, PRAGMA foreign_keys=ON y conexión thread-safe.
"""
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

# Ruta de la base de datos
DB_PATH = Path(__file__).parent.parent.parent / "data" / "ccr.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Thread-local storage para conexiones
_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """
    Obtiene una conexión SQLite thread-safe.
    Cada hilo tiene su propia conexión.
    """
    # Verificar si la conexión existe y no está cerrada
    need_new = False
    if not hasattr(_local, "conn") or _local.conn is None:
        need_new = True
    else:
        try:
            # Test si la conexión está viva
            _local.conn.execute("SELECT 1")
        except (sqlite3.ProgrammingError, AttributeError):
            need_new = True
    
    if need_new:
        _local.conn = sqlite3.connect(
            DB_PATH,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
            check_same_thread=False
        )
        _local.conn.row_factory = sqlite3.Row
        # Activar foreign keys
        _local.conn.execute("PRAGMA foreign_keys = ON")
        # WAL mode para mejor concurrencia
        _local.conn.execute("PRAGMA journal_mode = WAL")
        # Timeout para evitar bloqueos
        _local.conn.execute("PRAGMA busy_timeout = 5000")
    return _local.conn


@contextmanager
def transaction():
    """
    Context manager para transacciones.
    Uso:
        with transaction() as conn:
            conn.execute(...)
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def close_connection():
    """Cierra la conexión del hilo actual."""
    if hasattr(_local, "conn") and _local.conn is not None:
        _local.conn.close()
        _local.conn = None


def execute_query(query: str, params: tuple = ()) -> list[sqlite3.Row]:
    """Ejecuta una query SELECT y retorna todas las filas."""
    conn = get_connection()
    cursor = conn.execute(query, params)
    return cursor.fetchall()


def execute_one(query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
    """Ejecuta una query SELECT y retorna una fila."""
    conn = get_connection()
    cursor = conn.execute(query, params)
    return cursor.fetchone()


def execute_insert(query: str, params: tuple = ()) -> int:
    """Ejecuta un INSERT y retorna el lastrowid."""
    conn = get_connection()
    cursor = conn.execute(query, params)
    conn.commit()
    return cursor.lastrowid


def execute_update(query: str, params: tuple = ()) -> int:
    """Ejecuta un UPDATE/DELETE y retorna filas afectadas."""
    conn = get_connection()
    cursor = conn.execute(query, params)
    conn.commit()
    return cursor.rowcount


def execute_script(script: str):
    """Ejecuta un script SQL completo (múltiples statements)."""
    conn = get_connection()
    conn.executescript(script)
    conn.commit()


def vacuum():
    """Ejecuta VACUUM para optimizar la base de datos."""
    conn = get_connection()
    conn.execute("VACUUM")


def backup(backup_path: Path):
    """Crea una copia de seguridad de la base de datos."""
    conn = get_connection()
    with sqlite3.connect(backup_path) as dest:
        conn.backup(dest)


def get_db_version() -> int:
    """Obtiene la versión del esquema (user_version)."""
    conn = get_connection()
    cursor = conn.execute("PRAGMA user_version")
    return cursor.fetchone()[0]


def set_db_version(version: int):
    """Establece la versión del esquema."""
    conn = get_connection()
    conn.execute(f"PRAGMA user_version = {version}")
    conn.commit()