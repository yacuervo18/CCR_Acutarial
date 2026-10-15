from dataclasses import replace

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from asistente.config import CONFIGURACION, ConfiguracionAsistente
from asistente import conexion
from asistente.errores import registrar_error
from asistente import ui


def test_assistant_configuration_has_requested_defaults():
    assert CONFIGURACION.nombre_asistente == "Giru"
    assert CONFIGURACION.posicion == "derecha"
    assert CONFIGURACION.tamano_icono_px == 64
    assert ConfiguracionAsistente(posicion="izquierda").posicion == "izquierda"


def test_assistant_configuration_rejects_unsafe_or_invalid_css_values():
    with pytest.raises(ValueError):
        ConfiguracionAsistente(color_principal="red;position:fixed")


def test_assistant_icon_is_embedded_and_missing_icon_uses_fallback(monkeypatch, tmp_path):
    assert ui._leer_icono().startswith("data:image/webp;base64,")
    config = replace(CONFIGURACION, icono_ruta=str(tmp_path / "missing.png"))
    monkeypatch.setattr(ui, "CONFIGURACION", config)
    assert ui._leer_icono() is None


def test_enviar_pregunta_returns_simulated_echo():
    respuesta = conexion.enviar_pregunta("¿Qué haces?")
    assert "¿Qué haces?" in respuesta
    assert "todavía no estoy conectado" in respuesta.casefold()


def test_enviar_pregunta_handles_empty_text():
    assert conexion.enviar_pregunta("  ") == "Escribe una pregunta para que pueda ayudarte."


def test_enviar_pregunta_handles_internal_failure(monkeypatch):
    def fallar(texto, contexto=None):
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr(conexion, "_respuesta_simulada", fallar)
    assert "Inténtalo de nuevo" in conexion.enviar_pregunta("ayuda")


def test_registrar_error_redacts_paths_emails_and_values():
    try:
        raise ValueError(r"Fallo en C:\Users\persona\OneDrive Folder\datos.txt, para ana@empresa.com id 123456")
    except ValueError as error:
        registrar_error(error, "src.modulo")

    registro = st.session_state["asistente_ultimo_error"]
    assert registro["tipo"] == "ValueError"
    assert "C:\\Users" not in registro["mensaje"]
    assert "ana@empresa.com" not in registro["mensaje"]
    assert "123456" not in registro["mensaje"]
    assert len(registro["traceback_resumido"]) <= 3
    del st.session_state["asistente_ultimo_error"]


def test_assistant_renders_without_interfering_with_streamlit():
    app = AppTest.from_string(
        "from asistente.ui import mostrar_asistente\nmostrar_asistente()"
    ).run()
    assert not app.exception
    assert len(app.button) == 1
    opened = app.button[0].click().run()
    assert not opened.exception
    assert len(opened.chat_input) == 1
