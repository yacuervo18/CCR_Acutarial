"""Configuración visual y funcional del asistente de CCR."""

from dataclasses import dataclass
from pathlib import Path
import re


ASISTENTE_ACTIVO = True


@dataclass(frozen=True)
class ConfiguracionAsistente:
    """Opciones editables del asistente."""

    nombre_asistente: str = "Giru"
    icono_ruta: str = "assets/asistente/Giru_logo.webp"
    icono_respaldo: str = "🤖"
    tamano_icono_px: int = 64
    color_principal: str = "#185FA5"
    mensaje_bienvenida: str = "Hola, soy Giru, tu asistente."
    posicion: str = "derecha"
    ancho_ventana_px: int = 680
    alto_ventana_px: int = 500

    def __post_init__(self) -> None:
        """Valida los valores que se utilizan para construir el CSS."""
        if self.posicion not in {"izquierda", "derecha"}:
            raise ValueError("La posición debe ser 'izquierda' o 'derecha'.")
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", self.color_principal):
            raise ValueError("El color principal debe usar el formato hexadecimal #RRGGBB.")
        if not 32 <= self.tamano_icono_px <= 128:
            raise ValueError("El tamaño del icono debe estar entre 32 y 128 px.")
        if self.ancho_ventana_px < 280 or self.alto_ventana_px < 300:
            raise ValueError("El tamaño de la ventana de chat es demasiado pequeño.")


CONFIGURACION = ConfiguracionAsistente()
RAIZ_CCR = Path(__file__).resolve().parents[1]
