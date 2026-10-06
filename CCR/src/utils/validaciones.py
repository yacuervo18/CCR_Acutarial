"""
Utilidades de validación - Validaciones comunes.
"""
import re
from datetime import date
from typing import Optional, Tuple


def validar_email(email: str) -> bool:
    """Valida formato básico de email."""
    if not email:
        return True  # Opcional
    patron = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(patron, email))


def validar_url(url: str) -> bool:
    """Valida formato básico de URL http/https."""
    if not url:
        return False
    patron = r'^https?://[^\s/$.?#].[^\s]*$'
    return bool(re.match(patron, url))


def validar_ruta_red(ruta: str) -> bool:
    """Valida formato de ruta de red UNC (\\\\servidor\\carpeta)."""
    if not ruta:
        return False
    return ruta.startswith('\\\\') or ruta.startswith('//')


def validar_fecha_futura(fecha_str: str) -> Tuple[bool, str]:
    """Valida que la fecha no sea en el pasado (opcional: permitir hoy)."""
    try:
        fecha = date.fromisoformat(fecha_str)
        if fecha < date.today():
            return False, "La fecha no puede ser anterior a hoy"
        return True, ""
    except:
        return False, "Formato de fecha inválido (use YYYY-MM-DD)"


def validar_hora(hora_str: str) -> Tuple[bool, str]:
    """Valida formato HH:MM."""
    if not hora_str:
        return True, ""
    try:
        partes = hora_str.split(':')
        if len(partes) != 2:
            return False, "Formato debe ser HH:MM"
        h, m = int(partes[0]), int(partes[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            return False, "Hora inválida"
        return True, ""
    except:
        return False, "Formato de hora inválido"


def validar_codigo(codigo: str, patron: str = r'^[A-Z0-9_\-]+$') -> bool:
    """Valida código alfanumérico con guiones/underscores."""
    return bool(re.match(patron, codigo))


def validar_no_vacio(texto: str, campo: str = "Campo") -> Tuple[bool, str]:
    """Valida que no esté vacío ni solo espacios."""
    if not texto or not texto.strip():
        return False, f"{campo} es obligatorio"
    return True, ""


def validar_longitud(texto: str, max_len: int, campo: str = "Campo") -> Tuple[bool, str]:
    """Valida longitud máxima."""
    if len(texto) > max_len:
        return False, f"{campo} excede {max_len} caracteres"
    return True, ""


def validar_entero_positivo(valor: str, campo: str = "Valor") -> Tuple[bool, str, Optional[int]]:
    """Valida y convierte a entero positivo."""
    try:
        n = int(valor)
        if n <= 0:
            return False, f"{campo} debe ser positivo", None
        return True, "", n
    except:
        return False, f"{campo} debe ser un número entero", None


def sanitizar_sql(texto: str) -> str:
    """Sanitización básica para uso en LIKE (no para queries parametrizadas)."""
    return texto.replace('%', '\\%').replace('_', '\\_')