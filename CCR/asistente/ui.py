"""Interfaz flotante del asistente conversacional de CCR."""

import base64
import logging
from pathlib import Path
import xml.etree.ElementTree as ET

import streamlit as st

from .config import ASISTENTE_ACTIVO, CONFIGURACION, RAIZ_CCR
from .conexion import enviar_pregunta

logger = logging.getLogger(__name__)
_FORMATOS_ICONO = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml", ".webp": "image/webp"}
_HISTORIAL_KEY = "asistente_historial"
_ABIERTO_KEY = "asistente_abierto"
_ERROR_KEY = "asistente_ultimo_error"


def _leer_icono() -> str | None:
    """Devuelve el icono local como URI de datos o ``None`` si no es válido."""
    ruta = Path(CONFIGURACION.icono_ruta)
    if not ruta.is_absolute():
        ruta = RAIZ_CCR / ruta
    mime_type = _FORMATOS_ICONO.get(ruta.suffix.lower())
    if not mime_type:
        return None

    try:
        contenido = ruta.read_bytes()
        if mime_type == "image/svg+xml":
            svg_text = contenido.decode("utf-8")
            if "<!DOCTYPE" in svg_text.upper() or "<!ENTITY" in svg_text.upper():
                return None
            raiz = ET.fromstring(svg_text)
            if raiz.tag.rsplit("}", 1)[-1].lower() != "svg":
                return None
        codificado = base64.b64encode(contenido).decode("ascii")
    except (OSError, UnicodeDecodeError, ET.ParseError):
        logger.warning("No se pudo cargar el icono configurado para el asistente.")
        return None
    return f"data:{mime_type};base64,{codificado}"


def _inyectar_estilos(icono_uri: str | None) -> None:
    """Inyecta estilos acotados a los contenedores propios del asistente."""
    config = CONFIGURACION
    horizontal = "right" if config.posicion == "derecha" else "left"
    icon_background = f'background-image:url("{icono_uri}");' if icono_uri else ""
    label_style = "font-size:0;color:transparent;" if icono_uri else "font-size:1.8rem;"
    css = f"""
    <style>
    .st-key-asistente-launcher {{
        position:fixed !important; {horizontal}:20px; bottom:20px;
        z-index:10001; width:{config.tamano_icono_px}px; height:{config.tamano_icono_px}px;
    }}
    .st-key-asistente-launcher [data-testid="stButton"] {{width:100%; height:100%;}}
    .st-key-asistente-launcher [data-testid="stButton"] button {{
        width:{config.tamano_icono_px}px; height:{config.tamano_icono_px}px;
        border-radius:50%; border:2px solid white; padding:0;
        background-color:{config.color_principal}; {icon_background}
        background-position:center; background-repeat:no-repeat; background-size:cover;
        box-shadow:0 4px 16px rgba(0,0,0,.22); {label_style}
        transition:transform 140ms ease, box-shadow 140ms ease;
    }}
    .st-key-asistente-launcher [data-testid="stButton"] button:hover {{
        transform:translateY(-2px); box-shadow:0 6px 20px rgba(0,0,0,.27);
    }}
    .st-key-asistente-chat-panel {{
        position:fixed !important; {horizontal}:20px; bottom:{config.tamano_icono_px + 36}px;
        z-index:10000; width:min({config.ancho_ventana_px}px, calc(100vw - 40px));
        max-height:min({config.alto_ventana_px}px, calc(100vh - 120px));
        overflow:hidden; box-sizing:border-box;
        background-color:#E9EEF3 !important; color:#263442 !important;
        opacity:1 !important; border:1px solid #AEBECD !important;
        border-radius:14px; padding:.75rem;
        box-shadow:0 12px 32px rgba(15,23,42,.34);
    }}
    .st-key-asistente-chat-panel > div,
    .st-key-asistente-chat-panel [data-testid="stVerticalBlock"] {{
        background-color:#E9EEF3 !important;
    }}
    .st-key-asistente-chat-panel [data-testid="stVerticalBlock"] {{gap:.45rem;}}
    .st-key-asistente-chat-panel [data-testid="stHorizontalBlock"]:first-child {{
        padding:.35rem .45rem; border-radius:9px;
        background-color:#D5E0EB !important;
        border-bottom:1px solid #AEBECD;
    }}
    .st-key-asistente-chat-panel [data-testid="stChatMessage"] {{
        padding:.35rem .55rem; border-radius:10px;
        background-color:#F8FAFC !important;
        border:1px solid #D1DAE3;
    }}
    @media (max-width:520px) {{
        .st-key-asistente-launcher {{ {horizontal}:16px; bottom:16px; }}
        .st-key-asistente-chat-panel {{
            {horizontal}:12px; bottom:{config.tamano_icono_px + 28}px;
            width:calc(100vw - 24px); max-height:calc(100vh - 112px);
        }}
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def _inicializar_historial() -> None:
    if _HISTORIAL_KEY not in st.session_state:
        st.session_state[_HISTORIAL_KEY] = []


def _agregar_mensaje(rol: str, contenido: str) -> None:
    st.session_state[_HISTORIAL_KEY].append({"role": rol, "content": contenido})


def _renderizar_conversacion() -> None:
    _inicializar_historial()
    config = CONFIGURACION
    with st.container(key="asistente-chat-panel"):
        header, clear = st.columns([4, 1], vertical_alignment="center")
        with header:
            st.markdown(f"**{config.nombre_asistente}**")
        with clear:
            if st.button("Limpiar", key="asistente-limpiar", help="Limpiar conversación"):
                st.session_state[_HISTORIAL_KEY] = []

        if not st.session_state[_HISTORIAL_KEY]:
            _agregar_mensaje("assistant", config.mensaje_bienvenida)

        mensajes = st.container(height=300, border=False)
        with mensajes:
            for mensaje in st.session_state[_HISTORIAL_KEY]:
                with st.chat_message(mensaje["role"], avatar=config.icono_respaldo if mensaje["role"] == "assistant" else None):
                    st.text(mensaje["content"])

        error = st.session_state.get(_ERROR_KEY)
        if error and st.button("Preguntar sobre el último error", key="asistente-preguntar-error"):
            pregunta = "Ayúdame a comprender el último error registrado."
            _agregar_mensaje("user", pregunta)
            _responder(pregunta, {"ultimo_error": error})
            st.rerun()

        pregunta = st.chat_input("Escribe tu pregunta…", key="asistente-entrada", max_chars=1000)
        if pregunta:
            _agregar_mensaje("user", pregunta)
            _responder(pregunta)
            st.rerun()


def _responder(pregunta: str, contexto: dict | None = None) -> None:
    with st.spinner(f"{CONFIGURACION.nombre_asistente} está escribiendo…"):
        respuesta = enviar_pregunta(pregunta, contexto)
    _agregar_mensaje("assistant", respuesta)


def _mostrar_asistente() -> None:
    icono_uri = _leer_icono()
    _inyectar_estilos(icono_uri)
    _inicializar_historial()
    if _ABIERTO_KEY not in st.session_state:
        st.session_state[_ABIERTO_KEY] = False

    with st.container(key="asistente-launcher"):
        etiqueta = " " if icono_uri else CONFIGURACION.icono_respaldo
        if st.button(
            etiqueta,
            key="asistente-alternar",
            help=f"Abrir o cerrar {CONFIGURACION.nombre_asistente}",
            use_container_width=True,
        ):
            estaba_abierto = st.session_state[_ABIERTO_KEY]
            st.session_state[_ABIERTO_KEY] = not estaba_abierto

    if st.session_state[_ABIERTO_KEY]:
        _renderizar_conversacion()


def mostrar_asistente() -> None:
    """Muestra el asistente; los fallos internos no deben interrumpir CCR."""
    if not ASISTENTE_ACTIVO:
        return
    try:
        _mostrar_asistente()
    except Exception:
        logger.exception("No se pudo renderizar el asistente de CCR.")
        st.caption("El asistente no está disponible temporalmente.")
