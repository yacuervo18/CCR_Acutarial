"""Interfaz flotante del asistente conversacional de CCR."""

import base64
import logging
from pathlib import Path
import xml.etree.ElementTree as ET

import streamlit as st

from .config import ASISTENTE_ACTIVO, CONFIGURACION, RAIZ_CCR
from .conexion import reiniciar_conversacion
from .github_gemini import Respuesta
from .router import PROVEEDOR_COPILOT, PROVEEDOR_GEMINI, PROVEEDORES, enviar_pregunta
from src.phase1.process_operation_contract import (
    PROCESS_OPERATION_BY_ID,
    reconocer_operacion,
)
from src.ui.process_operations import (
    get_pending_process_operation,
    render_operation_confirmation,
    request_process_operation,
)

logger = logging.getLogger(__name__)
_FORMATOS_ICONO = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml", ".webp": "image/webp"}
_HISTORIAL_LEGACY_KEY = "asistente_historial"
_PROVEEDOR_KEY = "asistente_proveedor"
_HISTORIAL_PREFIX = "asistente_historial_por_proveedor"
_ABIERTO_KEY = "asistente_abierto"
_ERROR_KEY = "asistente_ultimo_error"
_PREGUNTA_KEY = "asistente-texto-pregunta"


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
        position:fixed !important; {horizontal}:20px;
        top:max(76px, calc(100vh - {config.alto_ventana_px + config.tamano_icono_px + 36}px));
        z-index:10000; width:min({config.ancho_ventana_px}px, calc(100vw - 40px));
        height:min({config.alto_ventana_px}px, calc(100vh - 176px));
        overflow:visible; box-sizing:border-box;
        background-color:#FFFFFF !important; color:#24292F !important;
        opacity:1 !important; border:1px solid #D0D7DE !important;
        border-radius:16px; padding:.65rem .8rem;
        box-shadow:0 12px 32px rgba(15,23,42,.22);
    }}
    .st-key-asistente-chat-panel > div,
    .st-key-asistente-chat-panel [data-testid="stVerticalBlock"] {{
        background-color:#FFFFFF !important;
    }}
    .st-key-asistente-chat-panel [data-testid="stVerticalBlock"] {{gap:.35rem;}}
    .st-key-asistente-chat-panel [data-testid="stHorizontalBlock"]:first-child {{
        padding:.15rem .2rem .35rem; border-radius:0;
        background-color:#FFFFFF !important;
        border-bottom:1px solid #E5E7EB;
    }}
    .st-key-asistente-chat-panel [data-testid="stChatMessage"] {{
        margin:.25rem 0; padding:.45rem .6rem; border-radius:10px;
        background-color:#FFFFFF !important;
        border:1px solid #E5E7EB;
        font-size:14px; line-height:1.6;
    }}
    .st-key-asistente-chat-panel [data-testid="stText"] {{
        font-size:14px; line-height:1.6;
    }}
    .st-key-asistente-chat-panel [data-testid="stChatMessage"] [data-testid="stText"] pre {{
        margin:0; font:inherit; line-height:1.6;
        white-space:pre-wrap; overflow-wrap:anywhere;
    }}
    .st-key-asistente-chat-panel [data-testid="stMarkdownContainer"] p {{
        font-size:14px; line-height:1.6;
    }}
    .st-key-asistente-messages {{
        height:100% !important; min-height:0 !important;
    }}
    .st-key-asistente-messages > div {{
        min-height:max-content !important;
    }}
    .st-key-asistente-messages [data-testid="stChatMessage"] {{
        flex-shrink:0;
    }}
    .st-key-asistente-chat-panel [data-testid="stLayoutWrapper"]:has(> .st-key-asistente-messages) {{
        position:absolute !important; top:64px; right:.8rem; bottom:145px; left:.8rem;
        width:auto !important; height:auto !important; min-height:0 !important;
    }}
    .st-key-asistente-chat-panel [data-testid="stLayoutWrapper"]:has(> .st-key-asistente-composer) {{
        position:absolute !important; right:.8rem; bottom:.65rem; left:.8rem;
        z-index:2; width:auto !important; min-height:0 !important;
    }}
    .st-key-asistente-composer {{
        position:relative !important;
        width:100%; box-sizing:border-box; padding:.35rem .45rem .25rem;
        background:#FFFFFF !important;
        border-top:1px solid #E5E7EB;
        border-radius:0 0 12px 12px;
        gap:.35rem !important;
    }}
    .st-key-asistente-composer [data-testid="stHorizontalBlock"] {{
        flex-wrap:nowrap !important;
    }}
    .st-key-asistente-composer [data-testid="stHorizontalBlock"] [data-testid="stColumn"] {{
        min-width:0 !important;
    }}
    .st-key-asistente-composer [data-testid="stTextInput"] input {{
        font-size:13px; line-height:1.35; background:#FFFFFF;
    }}
    .st-key-asistente-composer [data-testid="stFormSubmitButton"] button {{
        min-height:36px; width:36px; min-width:36px; padding:0;
        border-radius:9px;
    }}
    .st-key-asistente-agent-picker [data-testid="stPopover"] > button {{
        min-height:30px; width:auto; padding:0 .55rem;
        border-radius:8px; font-size:12px; line-height:1;
    }}
    .st-key-asistente-agent-picker [data-testid="stHorizontalBlock"] {{
        flex-wrap:nowrap !important; align-items:center; gap:.4rem;
    }}
    .st-key-asistente-agent-picker [data-testid="stMarkdownContainer"] p {{
        margin:0; font-size:12px; line-height:1.2; white-space:nowrap;
    }}
    .st-key-asistente-agent-picker button {{
        min-height:30px; padding:.2rem .5rem; font-size:12px;
        white-space:nowrap;
    }}
    .st-key-asistente-agent-picker [data-testid="stButton"] button {{
        min-height:32px; font-size:12px; white-space:nowrap;
    }}
    .st-key-asistente-chat-panel [data-testid="stButton"] button,
    .st-key-asistente-chat-panel [data-testid="stFormSubmitButton"] button {{
        min-height:36px; border-radius:9px; font-size:13px;
    }}
    .st-key-asistente-chat-panel [data-testid="stHorizontalBlock"]:first-child
        [data-testid="stColumn"]:last-child [data-testid="stButton"] {{
        display:flex; justify-content:flex-end;
    }}
    .st-key-asistente-chat-panel [data-testid="stHorizontalBlock"]:first-child
        [data-testid="stButton"] button {{
        min-height:30px; width:32px; min-width:32px; padding:0;
    }}
    .st-key-asistente-composer [data-testid="stHorizontalBlock"]
        [data-testid="stColumn"]:last-child [data-testid="stFormSubmitButton"] {{
        display:flex; justify-content:flex-end;
    }}
    @media (max-width:520px) {{
        .st-key-asistente-launcher {{ {horizontal}:16px; bottom:16px; }}
        .st-key-asistente-chat-panel {{
            {horizontal}:12px; top:max(68px, calc(100vh - {config.alto_ventana_px + config.tamano_icono_px + 28}px));
            width:calc(100vw - 24px); height:min({config.alto_ventana_px}px, calc(100vh - 156px));
            padding:.55rem;
        }}
        .st-key-asistente-messages {{
            height:100% !important;
        }}
        .st-key-asistente-composer {{
            padding:.3rem .35rem .2rem;
        }}
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def _clave_historial(proveedor: str) -> str:
    sufijo = "copilot" if proveedor == PROVEEDOR_COPILOT else "gemini"
    return f"{_HISTORIAL_PREFIX}_{sufijo}"


def _nombre_visible_agente(proveedor: str) -> str:
    return "Giru" if proveedor == PROVEEDOR_GEMINI else proveedor


def _historial(proveedor: str) -> list[dict]:
    clave = _clave_historial(proveedor)
    if clave not in st.session_state:
        if proveedor == PROVEEDOR_COPILOT and _HISTORIAL_LEGACY_KEY in st.session_state:
            st.session_state[clave] = st.session_state.pop(_HISTORIAL_LEGACY_KEY)
        else:
            st.session_state[clave] = []
    return st.session_state[clave]


def _agregar_mensaje(
    proveedor: str,
    rol: str,
    contenido: str,
    fuentes: tuple = (),
) -> None:
    mensaje = {"role": rol, "content": contenido}
    if fuentes:
        mensaje["sources"] = [
            {"title": fuente.titulo, "url": fuente.url}
            for fuente in fuentes
        ]
    _historial(proveedor).append(mensaje)


def _renderizar_conversacion(
    period: str | None = None,
    readonly: bool = False,
) -> None:
    if _PROVEEDOR_KEY not in st.session_state:
        st.session_state[_PROVEEDOR_KEY] = PROVEEDOR_COPILOT
    proveedor = st.session_state[_PROVEEDOR_KEY]
    historial = _historial(proveedor)
    config = CONFIGURACION
    with st.container(key="asistente-chat-panel"):
        header, clear = st.columns([20, 1], vertical_alignment="center")
        with header:
            st.markdown(f"**{config.nombre_asistente}**")
        with clear:
            if st.button(
                " ",
                key="asistente-limpiar",
                help="Limpiar conversación",
                icon=":material/delete_outline:",
                type="tertiary",
                width=32,
            ):
                historial.clear()
                if proveedor == PROVEEDOR_COPILOT:
                    reiniciar_conversacion()

        if not historial:
            _agregar_mensaje(proveedor, "assistant", config.mensaje_bienvenida)

        mensajes = st.container(height=324, border=False, key="asistente-messages")
        with mensajes:
            for indice, mensaje in enumerate(historial):
                with st.chat_message(mensaje["role"], avatar=config.icono_respaldo if mensaje["role"] == "assistant" else None):
                    st.text(mensaje["content"])
                    for fuente_indice, fuente in enumerate(mensaje.get("sources", [])):
                        st.link_button(
                            fuente["title"],
                            fuente["url"],
                        )
            resultado_operacion = render_operation_confirmation(
                "giru",
                period,
                readonly,
            )
            if resultado_operacion is not None:
                _agregar_mensaje(
                    proveedor,
                    "assistant",
                    resultado_operacion.message,
                )
                st.rerun()

        error = st.session_state.get(_ERROR_KEY)
        if error and st.button("Preguntar sobre el último error", key="asistente-preguntar-error"):
            pregunta = "Ayúdame a comprender el último error registrado."
            historial_previo = list(historial)
            _agregar_mensaje(proveedor, "user", pregunta)
            with mensajes:
                _responder(proveedor, pregunta, {"ultimo_error": error}, historial_previo)
            st.rerun()

        with st.container(key="asistente-composer"):
            with st.form("asistente-enviar-form", clear_on_submit=True):
                entrada, envio = st.columns([1, 0.14], vertical_alignment="center")
                with entrada:
                    pregunta = st.text_input(
                        "Pregunta",
                        key=_PREGUNTA_KEY,
                        max_chars=1000,
                        placeholder="Escribe tu pregunta…",
                        label_visibility="collapsed",
                    )
                with envio:
                    enviar = st.form_submit_button(
                        " ",
                        key="asistente-enviar",
                        help="Enviar pregunta",
                        icon=":material/send:",
                        type="primary",
                        width=36,
                    )

            agente_actual = st.session_state[_PROVEEDOR_KEY]
            with st.container(key="asistente-agent-picker"):
                selector, activo = st.columns([1, 1.8], vertical_alignment="center")
                with selector:
                    with st.popover(
                        "Agente",
                        help="Seleccionar agente",
                        icon=":material/keyboard_arrow_down:",
                        width="content",
                    ):
                        for agente in PROVEEDORES:
                            if st.button(
                                _nombre_visible_agente(agente),
                                key=f"asistente-agente-{agente.lower().replace(' ', '-')}",
                                type="primary" if agente == agente_actual else "tertiary",
                                use_container_width=True,
                            ):
                                st.session_state[_PROVEEDOR_KEY] = agente
                                st.rerun()
                with activo:
                    st.markdown(
                        f"Responderá: **{_nombre_visible_agente(agente_actual)}**"
                    )

    if enviar and pregunta.strip():
        operation = (
            reconocer_operacion(pregunta)
            if proveedor == PROVEEDOR_GEMINI
            else None
        )
        if operation is not None:
            _agregar_mensaje(proveedor, "user", pregunta)
            if not operation.requestable:
                _agregar_mensaje(
                    proveedor,
                    "assistant",
                    operation.unavailable_message,
                )
            elif readonly:
                _agregar_mensaje(
                    proveedor,
                    "assistant",
                    "El periodo seleccionado es de solo lectura; no se registró "
                    "ninguna solicitud operativa.",
                )
            elif period is None:
                _agregar_mensaje(
                    proveedor,
                    "assistant",
                    "No pude asociar la solicitud a un periodo. No se inició "
                    "ninguna operación.",
                )
            else:
                request = request_process_operation(
                    operation.identifier,
                    "giru",
                    period,
                )
                if request is None:
                    pending = get_pending_process_operation()
                    pending_operation = (
                        PROCESS_OPERATION_BY_ID[pending["operation_id"]]
                        if pending
                        else None
                    )
                    pending_label = (
                        pending_operation.label
                        if pending_operation
                        else "otra operación"
                    )
                    _agregar_mensaje(
                        proveedor,
                        "assistant",
                        "Ya hay una solicitud pendiente de confirmación "
                        f"({pending_label}). Confírmala o cancélala antes de "
                        "iniciar otra.",
                    )
                else:
                    _agregar_mensaje(
                        proveedor,
                        "assistant",
                        f"Entendí que solicitas «{operation.label}». "
                        f"{operation.confirmation_prompt}",
                    )
        else:
            historial_previo = list(historial)
            _agregar_mensaje(proveedor, "user", pregunta)
            with mensajes:
                _responder(proveedor, pregunta, historial_previo=historial_previo)
        st.rerun()
    elif enviar:
        st.info("Escribe una pregunta antes de enviar.")


def _responder(
    proveedor: str,
    pregunta: str,
    contexto: dict | None = None,
    historial_previo: list[dict] | None = None,
) -> None:
    with st.chat_message("user"):
        st.text(pregunta)
    with st.chat_message("assistant", avatar=CONFIGURACION.icono_respaldo):
        with st.spinner(f"{CONFIGURACION.nombre_asistente} está escribiendo…"):
            respuesta = enviar_pregunta(
                proveedor,
                pregunta,
                contexto,
                [
                    {"role": mensaje["role"], "content": mensaje["content"]}
                    for mensaje in (historial_previo or [])[-6:]
                    if mensaje.get("role") in {"user", "assistant"}
                ],
            )
    if isinstance(respuesta, Respuesta):
        _agregar_mensaje(proveedor, "assistant", respuesta.texto, respuesta.fuentes)
    else:
        _agregar_mensaje(proveedor, "assistant", respuesta)


def _mostrar_asistente(
    period: str | None = None,
    readonly: bool = False,
) -> None:
    icono_uri = _leer_icono()
    _inyectar_estilos(icono_uri)
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
        _renderizar_conversacion(period, readonly)


def mostrar_asistente(
    period: str | None = None,
    readonly: bool = False,
) -> None:
    """Muestra el asistente; los fallos internos no deben interrumpir CCR."""
    if not ASISTENTE_ACTIVO:
        return
    try:
        _mostrar_asistente(period, readonly)
    except Exception:
        logger.exception("No se pudo renderizar el asistente de CCR.")
        st.caption("El asistente no está disponible temporalmente.")
