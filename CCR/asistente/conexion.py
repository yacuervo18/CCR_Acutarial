"""Conexión del asistente de CCR con Microsoft Copilot Studio mediante Direct Line."""

from dataclasses import dataclass
import logging
import time
from urllib.parse import urlsplit
from uuid import uuid4

import requests
import streamlit as st

from .http_transport import session_with_system_trust

logger = logging.getLogger(__name__)

_SESSION_KEY = "asistente_direct_line"
_API_PATH = "/v3/directline"
_REQUEST_TIMEOUT = (5, 10)
_RESPONSE_TIMEOUT_SECONDS = 45
_POLL_INTERVAL_SECONDS = 1
_TOKEN_REFRESH_MARGIN_SECONDS = 60


@dataclass(frozen=True)
class _ConfiguracionDirectLine:
    """Valores privados de conexión disponibles solo en el servidor."""

    endpoint: str
    secreto: str


class _ErrorConfiguracionDirectLine(Exception):
    """Indica que faltan valores válidos de configuración."""


class _ErrorDirectLine(Exception):
    """Indica un error de comunicación con Direct Line."""

    def __init__(self, mensaje: str, estado_http: int | None = None) -> None:
        super().__init__(mensaje)
        self.estado_http = estado_http


def _leer_configuracion() -> _ConfiguracionDirectLine:
    """Lee el endpoint y el secreto desde ``st.secrets``."""
    try:
        valores = st.secrets["copilot_studio"]
    except (KeyError, FileNotFoundError) as error:
        raise _ErrorConfiguracionDirectLine from error

    endpoint = valores.get("direct_line_base_url", "")
    secreto = valores.get("direct_line_secret", "")
    if not isinstance(endpoint, str) or not isinstance(secreto, str):
        raise _ErrorConfiguracionDirectLine

    endpoint = endpoint.strip().rstrip("/")
    try:
        partes = urlsplit(endpoint)
    except ValueError as error:
        raise _ErrorConfiguracionDirectLine from error
    if (
        partes.scheme != "https"
        or not partes.netloc
        or partes.path not in {"", "/"}
        or partes.query
        or partes.fragment
        or not secreto.strip()
    ):
        raise _ErrorConfiguracionDirectLine

    return _ConfiguracionDirectLine(endpoint=endpoint, secreto=secreto.strip())


def _solicitar_json(
    configuracion: _ConfiguracionDirectLine,
    metodo: str,
    ruta: str,
    credencial: str,
    contenido: dict[str, object] | None = None,
    parametros: dict[str, str] | None = None,
) -> dict[str, object]:
    """Realiza una solicitud REST sin registrar ni exponer credenciales."""
    try:
        with session_with_system_trust() as sesion:
            respuesta = sesion.request(
                metodo,
                f"{configuracion.endpoint}{_API_PATH}{ruta}",
                headers={"Authorization": f"Bearer {credencial}"},
                json=contenido,
                params=parametros,
                timeout=_REQUEST_TIMEOUT,
            )
        respuesta.raise_for_status()
        resultado = respuesta.json()
    except requests.HTTPError as error:
        estado = error.response.status_code if error.response is not None else None
        raise _ErrorDirectLine("Direct Line rechazó la solicitud.", estado) from error
    except requests.RequestException as error:
        raise _ErrorDirectLine("No fue posible comunicarse con Direct Line.") from error
    except ValueError as error:
        raise _ErrorDirectLine("Direct Line devolvió una respuesta no válida.") from error

    if not isinstance(resultado, dict):
        raise _ErrorDirectLine("Direct Line devolvió una respuesta no válida.")
    return resultado


def _guardar_estado(
    conversacion: dict[str, object],
    usuario_id: str,
    marca: str | None = None,
) -> dict[str, object]:
    token = conversacion.get("token")
    id_conversacion = conversacion.get("conversationId")
    duracion = conversacion.get("expires_in")
    if (
        not isinstance(token, str)
        or not token
        or not isinstance(id_conversacion, str)
        or not id_conversacion
        or not isinstance(duracion, (int, float))
        or duracion <= 0
    ):
        raise _ErrorDirectLine("Direct Line no devolvió datos válidos de conversación.")

    estado = {
        "token": token,
        "conversation_id": id_conversacion,
        "user_id": usuario_id,
        "expires_at": time.time() + float(duracion),
    }
    if marca is not None:
        estado["watermark"] = marca
    st.session_state[_SESSION_KEY] = estado
    return estado


def _crear_conversacion(
    configuracion: _ConfiguracionDirectLine,
) -> dict[str, object]:
    """Inicia una conversación; el secreto nunca sale del servidor."""
    usuario_id = f"ccr_{uuid4().hex}"
    conversacion = _solicitar_json(
        configuracion,
        "POST",
        "/conversations",
        configuracion.secreto,
        contenido={"user": {"id": usuario_id}},
    )
    return _guardar_estado(conversacion, usuario_id)


def _obtener_conversacion(
    configuracion: _ConfiguracionDirectLine,
) -> dict[str, object]:
    estado = st.session_state.get(_SESSION_KEY)
    if not isinstance(estado, dict):
        return _crear_conversacion(configuracion)

    id_conversacion = estado.get("conversation_id")
    token = estado.get("token")
    usuario_id = estado.get("user_id")
    vence = estado.get("expires_at")
    if (
        not isinstance(id_conversacion, str)
        or not isinstance(token, str)
        or not isinstance(usuario_id, str)
        or not isinstance(vence, (int, float))
    ):
        return _crear_conversacion(configuracion)

    if vence > time.time() + _TOKEN_REFRESH_MARGIN_SECONDS:
        return estado

    try:
        conversacion = _solicitar_json(
            configuracion,
            "POST",
            "/tokens/refresh",
            token,
        )
    except _ErrorDirectLine as error:
        if error.estado_http not in {401, 403}:
            raise
        return _crear_conversacion(configuracion)

    conversacion.setdefault("conversationId", id_conversacion)
    marca = estado.get("watermark")
    return _guardar_estado(
        conversacion,
        usuario_id,
        marca if isinstance(marca, str) else None,
    )


def _esperar_respuesta(
    configuracion: _ConfiguracionDirectLine,
    estado: dict[str, object],
) -> str:
    fin = time.monotonic() + _RESPONSE_TIMEOUT_SECONDS
    while time.monotonic() < fin:
        parametros = {}
        marca = estado.get("watermark")
        if isinstance(marca, str):
            parametros["watermark"] = marca

        actividad = _solicitar_json(
            configuracion,
            "GET",
            f"/conversations/{estado['conversation_id']}/activities",
            estado["token"],
            parametros=parametros or None,
        )
        actividades = actividad.get("activities", [])
        marca_nueva = actividad.get("watermark")
        if isinstance(marca_nueva, str):
            estado["watermark"] = marca_nueva
            st.session_state[_SESSION_KEY] = estado

        respuestas = []
        for elemento in actividades if isinstance(actividades, list) else []:
            if not isinstance(elemento, dict) or elemento.get("type") != "message":
                continue
            remitente = elemento.get("from")
            if not isinstance(remitente, dict) or remitente.get("id") == estado["user_id"]:
                continue
            texto = elemento.get("text")
            if isinstance(texto, str) and texto.strip():
                respuestas.append(texto.strip())

        if respuestas:
            return "\n\n".join(respuestas)
        time.sleep(_POLL_INTERVAL_SECONDS)

    return "El agente no respondió a tiempo. Inténtalo de nuevo en unos momentos."


def _crear_mensaje(texto: str, contexto: dict | None) -> str:
    """Añade únicamente el resumen de error solicitado explícitamente."""
    if not isinstance(contexto, dict):
        return texto
    error = contexto.get("ultimo_error")
    if not isinstance(error, dict):
        return texto

    campos = []
    for clave, etiqueta in (
        ("tipo", "Tipo"),
        ("mensaje", "Mensaje"),
        ("origen", "Origen"),
    ):
        valor = error.get(clave)
        if isinstance(valor, str) and valor.strip():
            campos.append(f"{etiqueta}: {valor[:240]}")
    traceback_resumido = error.get("traceback_resumido")
    if isinstance(traceback_resumido, list):
        ubicaciones = [
            linea[:120]
            for linea in traceback_resumido[:3]
            if isinstance(linea, str) and linea.strip()
        ]
        if ubicaciones:
            campos.append("Ubicaciones: " + "; ".join(ubicaciones))

    if not campos:
        return texto
    return f"{texto}\n\nResumen técnico del último error:\n" + "\n".join(campos)


def reiniciar_conversacion() -> None:
    """Olvida la conversación remota al limpiar el historial visible."""
    st.session_state.pop(_SESSION_KEY, None)


def enviar_pregunta(texto: str, contexto: dict | None = None) -> str:
    """Envía la pregunta al agente por Direct Line y devuelve su respuesta."""
    pregunta = texto.strip() if isinstance(texto, str) else ""
    if not pregunta:
        return "Escribe una pregunta para que pueda ayudarte."

    try:
        configuracion = _leer_configuracion()
        estado = _obtener_conversacion(configuracion)
        mensaje = _crear_mensaje(pregunta, contexto)
        _solicitar_json(
            configuracion,
            "POST",
            f"/conversations/{estado['conversation_id']}/activities",
            estado["token"],
            contenido={
                "type": "message",
                "from": {"id": estado["user_id"]},
                "text": mensaje,
            },
        )
        return _esperar_respuesta(configuracion, estado)
    except _ErrorConfiguracionDirectLine:
        return (
            "Direct Line aún no está configurado. Añade la URL base y el secreto "
            "en la configuración privada de Streamlit."
        )
    except _ErrorDirectLine:
        logger.exception("Falló la comunicación entre CCR y Copilot Studio.")
        return (
            "No pude comunicarme con el agente en este momento. "
            "Inténtalo de nuevo o contacta al administrador."
        )
