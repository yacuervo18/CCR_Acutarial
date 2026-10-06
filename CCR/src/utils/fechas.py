"""
Utilidades de fechas - Formateo y parsing.
"""
from datetime import date, datetime
from typing import Optional


def formatear_fecha(fecha_str: Optional[str], formato: str = "%d/%m/%Y") -> str:
    """Convierte fecha ISO a formato dd/mm/aaaa."""
    if not fecha_str:
        return "—"
    try:
        return date.fromisoformat(fecha_str).strftime(formato)
    except:
        return fecha_str


def formatear_datetime(dt_str: Optional[str], formato: str = "%d/%m/%Y %H:%M") -> str:
    """Convierte datetime ISO a formato dd/mm/aaaa HH:MM."""
    if not dt_str:
        return "—"
    try:
        return datetime.fromisoformat(dt_str).strftime(formato)
    except:
        return dt_str


def parse_fecha(fecha_str: str) -> Optional[date]:
    """Parsea fecha dd/mm/aaaa a date."""
    try:
        return datetime.strptime(fecha_str, "%d/%m/%Y").date()
    except:
        try:
            return date.fromisoformat(fecha_str)
        except:
            return None


def hoy_iso() -> str:
    return date.today().isoformat()


def ahora_iso() -> str:
    return datetime.now().isoformat()


def dias_hasta(fecha_limite: str) -> Optional[int]:
    """Días desde hoy hasta fecha_limite (negativo si vencida)."""
    try:
        lim = date.fromisoformat(fecha_limite)
        return (lim - date.today()).days
    except:
        return None


def es_dia_habil(fecha: date) -> bool:
    """Verifica si es día hábil (lunes-viernes)."""
    return fecha.weekday() < 5


def proximo_dia_habil(fecha: date) -> date:
    """Retorna el siguiente día hábil."""
    while not es_dia_habil(fecha):
        fecha = date.fromordinal(fecha.toordinal() + 1)
    return fecha