"""Enruta las preguntas de Giru al proveedor seleccionado por el usuario."""

from . import conexion
from .github_gemini import Respuesta, responder

PROVEEDOR_COPILOT = "Copilot Studio"
PROVEEDOR_GEMINI = "Gemini"
PROVEEDORES = (PROVEEDOR_COPILOT, PROVEEDOR_GEMINI)

_MENSAJE_PERMISOS_COPILOT = (
    "Aún no tenemos los permisos para utilizar Microsoft 365 Copilot, pero no te "
    "preocupes: haz clic en Agente y cambia a Giru. Giru es un agente diseñado y "
    "desarrollado para ayudarte a gestionar tareas del área."
)


def enviar_pregunta(
    proveedor: str,
    texto: str,
    contexto: dict | None = None,
    historial: list[dict[str, str]] | None = None,
) -> str | Respuesta:
    """Usa solo el motor seleccionado; no hace fallback automático entre proveedores."""
    if proveedor == PROVEEDOR_COPILOT:
        respuesta = conexion.enviar_pregunta(texto, contexto)
        if "IntegratedAuthenticationNotSupportedInChannel" in respuesta:
            return _MENSAJE_PERMISOS_COPILOT
        return respuesta
    if proveedor == PROVEEDOR_GEMINI:
        return responder(texto, contexto, historial)
    raise ValueError("El proveedor seleccionado para Giru no está admitido.")
