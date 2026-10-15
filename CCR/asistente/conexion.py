"""Punto de conexión intercambiable para el asistente de CCR."""

import logging

logger = logging.getLogger(__name__)


def _respuesta_simulada(texto: str, contexto: dict | None = None) -> str:
    """Genera una respuesta local sin enviar información fuera de CCR."""
    del contexto
    return (
        f"Recibí tu pregunta: “{texto}”\n\n"
        "Todavía no estoy conectado al agente de Microsoft Copilot Studio; "
        "esta es una respuesta simulada."
    )


def enviar_pregunta(texto: str, contexto: dict | None = None) -> str:
    """Responde de forma simulada y ofrece un punto único para la conexión futura.

    En una fase posterior, solo se reemplazará la implementación de esta función
    para llamar a Copilot Studio (por iframe o Direct Line, según se defina).
    La configuración futura se leerá en el servidor desde ``st.secrets``; no se
    incluirán URLs ni tokens en el código ni se enviarán al navegador.
    """
    pregunta = texto.strip() if isinstance(texto, str) else ""
    if not pregunta:
        return "Escribe una pregunta para que pueda ayudarte."

    try:
        respuesta = _respuesta_simulada(pregunta, contexto)
    except Exception:
        logger.exception("Falló la respuesta simulada del asistente.")
        return "No pude preparar una respuesta en este momento. Inténtalo de nuevo."

    if not isinstance(respuesta, str) or not respuesta.strip():
        return "No recibí una respuesta válida. Inténtalo de nuevo."
    return respuesta.strip()
