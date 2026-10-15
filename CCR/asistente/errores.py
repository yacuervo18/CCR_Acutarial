"""Registro sanitizado de errores para consultas del asistente."""

from datetime import datetime
import re
import traceback

import streamlit as st


_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_WINDOWS_PATH_RE = re.compile(r"\b[A-Za-z]:\\[^\r\n,;\"']+")
_UNIX_PATH_RE = re.compile(r"(?<!\w)/(?:[^/\s]+/)+[^/\s]*")
_LONG_NUMBER_RE = re.compile(r"\b\d{5,}\b")


def _sanitizar_mensaje(mensaje: str) -> str:
    """Retira rutas, correos e identificadores numéricos del mensaje."""
    mensaje = _EMAIL_RE.sub("[correo oculto]", mensaje)
    mensaje = _WINDOWS_PATH_RE.sub("[ruta oculta]", mensaje)
    mensaje = _UNIX_PATH_RE.sub("[ruta oculta]", mensaje)
    mensaje = _LONG_NUMBER_RE.sub("[identificador oculto]", mensaje)
    return mensaje[:240]


def registrar_error(excepcion: Exception, origen: str) -> None:
    """Guarda un resumen acotado sin valores locales ni rutas de archivos."""
    frames = traceback.extract_tb(excepcion.__traceback__)[-3:]
    resumen = [
        f"{frame.name} (línea {frame.lineno})"
        for frame in frames
    ]
    st.session_state["asistente_ultimo_error"] = {
        "tipo": type(excepcion).__name__,
        "mensaje": _sanitizar_mensaje(str(excepcion)) or "Mensaje técnico no disponible.",
        "traceback_resumido": resumen,
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "origen": _sanitizar_mensaje(origen) or "origen no especificado",
    }
