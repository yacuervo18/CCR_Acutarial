"""
Servicio de evidencias - Gestión de archivos y enlaces.
"""
import os
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Optional
import mimetypes
from src.database.db_manager import execute_query, execute_one, execute_insert, execute_update, transaction
from src.services.config_service import get_config


EVIDENCIAS_BASE = Path(__file__).parent.parent.parent / "data" / "evidencias"


def get_ruta_evidencia(año: int, mes: int, nombre_archivo: str) -> Path:
    """Genera ruta única para evidencia: data/evidencias/{año}/{mes}/nombre_seguro"""
    carpeta = EVIDENCIAS_BASE / str(año) / f"{mes:02d}"
    carpeta.mkdir(parents=True, exist_ok=True)
    
    # Nombre seguro: timestamp + nombre original sanitizado
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_seguro = "".join(c for c in nombre_archivo if c.isalnum() or c in "._- ")
    nombre_final = f"{timestamp}_{nombre_seguro}"
    
    # Evitar colisiones
    ruta = carpeta / nombre_final
    contador = 1
    while ruta.exists():
        nombre_final = f"{timestamp}_{contador}_{nombre_seguro}"
        ruta = carpeta / nombre_final
        contador += 1
    
    return ruta


def guardar_archivo_evidencia(
    archivo_bytes: bytes,
    nombre_original: str,
    tipo_evidencia_id: int,
    entidad_tipo: str,
    entidad_id: int,
    subido_por: str,
    descripcion: str = "",
    año: Optional[int] = None,
    mes: Optional[int] = None
) -> tuple[bool, str, Optional[dict]]:
    """Guarda archivo físico y registra en BD."""
    if año is None:
        año = date.today().year
    if mes is None:
        mes = date.today().month
    
    # Validar tamaño
    tipo_row = execute_one("SELECT tamaño_max_mb FROM tipos_evidencia WHERE id = ?", (tipo_evidencia_id,))
    max_mb = tipo_row["tamaño_max_mb"] if tipo_row else get_config("evidencias_tamaño_max_mb", "20")
    max_bytes = int(max_mb) * 1024 * 1024
    
    if len(archivo_bytes) > max_bytes:
        return False, f"Archivo supera el límite de {max_mb} MB", None
    
    # Guardar archivo
    ruta_relativa = get_ruta_evidencia(año, mes, nombre_original)
    try:
        ruta_relativa.write_bytes(archivo_bytes)
    except Exception as e:
        return False, f"Error guardando archivo: {e}", None
    
    # Detectar MIME
    mime_type, _ = mimetypes.guess_type(nombre_original)
    
    # Registrar en BD
    ruta_db = str(ruta_relativa.relative_to(EVIDENCIAS_BASE.parent.parent))
    
    evidencia_id = execute_insert(
        """INSERT INTO evidencias 
           (tipo_evidencia_id, entidad_tipo, entidad_id, nombre_archivo, nombre_original, 
            ruta_relativa, tamaño_bytes, mime_type, es_enlace, subido_por, descripcion)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
        (tipo_evidencia_id, entidad_tipo, entidad_id, ruta_relativa.name, nombre_original,
         ruta_db, len(archivo_bytes), mime_type, subido_por, descripcion)
    )
    
    evidencia = get_evidencia_by_id(evidencia_id)
    return True, "Evidencia guardada.", evidencia


def registrar_enlace_evidencia(
    url: str,
    tipo_evidencia_id: int,
    entidad_tipo: str,
    entidad_id: int,
    subido_por: str,
    descripcion: str = "",
    nombre_original: str = ""
) -> tuple[bool, str, Optional[dict]]:
    """Registra solo un enlace/ruta de red como evidencia."""
    if not nombre_original:
        nombre_original = url
    
    evidencia_id = execute_insert(
        """INSERT INTO evidencias 
           (tipo_evidencia_id, entidad_tipo, entidad_id, nombre_archivo, nombre_original, 
            ruta_relativa, tamaño_bytes, mime_type, es_enlace, enlace_url, subido_por, descripcion)
           VALUES (?, ?, ?, ?, ?, '', 0, '', 1, ?, ?, ?)""",
        (tipo_evidencia_id, entidad_tipo, entidad_id, nombre_original, nombre_original,
         url, subido_por, descripcion)
    )
    
    evidencia = get_evidencia_by_id(evidencia_id)
    return True, "Enlace registrado.", evidencia


def get_evidencia_by_id(evidencia_id: int) -> Optional[dict]:
    row = execute_one("""
        SELECT e.*, te.codigo as tipo_codigo, te.nombre as tipo_nombre
        FROM evidencias e
        JOIN tipos_evidencia te ON e.tipo_evidencia_id = te.id
        WHERE e.id = ?
    """, (evidencia_id,))
    return dict(row) if row else None


def get_evidencias_entidad(entidad_tipo: str, entidad_id: int) -> list[dict]:
    rows = execute_query("""
        SELECT e.*, te.codigo as tipo_codigo, te.nombre as tipo_nombre
        FROM evidencias e
        JOIN tipos_evidencia te ON e.tipo_evidencia_id = te.id
        WHERE e.entidad_tipo = ? AND e.entidad_id = ? AND e.activo = 1
        ORDER BY e.subido_en DESC
    """, (entidad_tipo, entidad_id))
    return [dict(row) for row in rows]


def get_evidencias_filtros(
    tipo_evidencia_id: Optional[int] = None,
    entidad_tipo: Optional[str] = None,
    proceso_id: Optional[int] = None,
    año: Optional[int] = None,
    mes: Optional[int] = None
) -> list[dict]:
    conditions = ["e.activo = 1"]
    params = []
    
    if tipo_evidencia_id:
        conditions.append("e.tipo_evidencia_id = ?")
        params.append(tipo_evidencia_id)
    if entidad_tipo:
        conditions.append("e.entidad_tipo = ?")
        params.append(entidad_tipo)
    if proceso_id:
        # Buscar evidencias de proceso, subtareas, controles, aprobaciones de ese proceso
        conditions.append("""
            (e.entidad_tipo = 'proceso' AND e.entidad_id = ?)
            OR (e.entidad_tipo = 'subtarea' AND e.entidad_id IN (SELECT id FROM subtareas WHERE proceso_id = ?))
            OR (e.entidad_tipo = 'control_sox' AND e.entidad_id IN (SELECT id FROM controles_sox WHERE cierre_id IN (SELECT cierre_id FROM procesos WHERE id = ?)))
            OR (e.entidad_tipo = 'aprobacion' AND e.entidad_id IN (SELECT id FROM aprobaciones WHERE proceso_id = ?))
        """)
        params.extend([proceso_id, proceso_id, proceso_id, proceso_id])
    if año:
        conditions.append("strftime('%Y', e.subido_en) = ?")
        params.append(str(año))
    if mes:
        conditions.append("strftime('%m', e.subido_en) = ?")
        params.append(f"{mes:02d}")
    
    where = "WHERE " + " AND ".join(conditions)
    
    rows = execute_query(f"""
        SELECT e.*, te.codigo as tipo_codigo, te.nombre as tipo_nombre
        FROM evidencias e
        JOIN tipos_evidencia te ON e.tipo_evidencia_id = te.id
        {where}
        ORDER BY e.subido_en DESC
    """, tuple(params))
    return [dict(row) for row in rows]


def get_ruta_absoluta_evidencia(evidencia: dict) -> Path:
    """Obtiene ruta absoluta del archivo físico."""
    return EVIDENCIAS_BASE.parent.parent / evidencia["ruta_relativa"]


def eliminar_evidencia(evidencia_id: int) -> tuple[bool, str]:
    """Borra lógico y opcionalmente archivo físico."""
    evidencia = get_evidencia_by_id(evidencia_id)
    if not evidencia:
        return False, "Evidencia no encontrada."
    
    # Borrado lógico
    execute_update("UPDATE evidencias SET activo = 0 WHERE id = ?", (evidencia_id,))
    
    # Opcional: borrar archivo físico si no es enlace
    if not evidencia["es_enlace"]:
        try:
            ruta = get_ruta_absoluta_evidencia(evidencia)
            if ruta.exists():
                ruta.unlink()
        except Exception:
            pass  # No fallar si no se puede borrar el archivo
    
    return True, "Evidencia eliminada (borrado lógico)."