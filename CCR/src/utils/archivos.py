"""
Utilidades de archivos - Manejo de evidencias, nombres seguros, etc.
"""
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Optional


def nombre_seguro(nombre: str) -> str:
    """Sanitiza nombre de archivo para uso seguro en filesystem."""
    # Mantener alfanuméricos, puntos, guiones, underscores, espacios
    nombre = re.sub(r'[^\w\s\.\-]', '', nombre)
    # Reemplazar espacios múltiples por uno solo
    nombre = re.sub(r'\s+', ' ', nombre).strip()
    # Limitar longitud
    return nombre[:200]


def generar_nombre_unico(carpeta: Path, nombre_base: str) -> Path:
    """Genera nombre único en carpeta añadiendo timestamp y contador si hace falta."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_seguro_base = nombre_seguro(nombre_base)
    nombre_final = f"{timestamp}_{nombre_seguro_base}"
    ruta = carpeta / nombre_final
    
    contador = 1
    while ruta.exists():
        nombre_final = f"{timestamp}_{contador}_{nombre_seguro_base}"
        ruta = carpeta / nombre_final
        contador += 1
    
    return ruta


def formatear_tamaño(bytes_: int) -> str:
    """Formatea bytes a KB/MB/GB legible."""
    if bytes_ < 1024:
        return f"{bytes_} B"
    elif bytes_ < 1024 * 1024:
        return f"{bytes_ / 1024:.1f} KB"
    elif bytes_ < 1024 * 1024 * 1024:
        return f"{bytes_ / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_ / (1024 * 1024 * 1024):.1f} GB"


def obtener_mime_type(nombre_archivo: str) -> str:
    """Obtiene MIME type basado en extensión."""
    import mimetypes
    mime, _ = mimetypes.guess_type(nombre_archivo)
    return mime or "application/octet-stream"


def es_imagen(nombre_archivo: str) -> bool:
    ext = Path(nombre_archivo).suffix.lower()
    return ext in ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp']


def es_pdf(nombre_archivo: str) -> bool:
    return Path(nombre_archivo).suffix.lower() == '.pdf'


def es_excel(nombre_archivo: str) -> bool:
    ext = Path(nombre_archivo).suffix.lower()
    return ext in ['.xlsx', '.xls', '.csv']


def validar_extension(nombre_archivo: str, extensiones_permitidas: list[str]) -> bool:
    """Valida si la extensión está en la lista permitida."""
    if not extensiones_permitidas:
        return True  # Sin restricciones (enlaces)
    ext = Path(nombre_archivo).suffix.lower()
    return ext in [e.lower() for e in extensiones_permitidas]