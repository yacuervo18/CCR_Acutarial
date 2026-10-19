from dataclasses import replace
import ssl
from types import SimpleNamespace

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from asistente.config import CONFIGURACION, ConfiguracionAsistente
from asistente import conexion
from asistente.http_transport import SystemTrustStoreAdapter
from asistente.errores import registrar_error
from asistente import ui


def test_assistant_configuration_has_requested_defaults():
    assert CONFIGURACION.nombre_asistente == "Giru"
    assert CONFIGURACION.posicion == "derecha"
    assert CONFIGURACION.tamano_icono_px == 64
    assert CONFIGURACION.ancho_ventana_px == 680
    assert CONFIGURACION.alto_ventana_px == 500
    assert ConfiguracionAsistente(posicion="izquierda").posicion == "izquierda"


def test_assistant_configuration_rejects_unsafe_or_invalid_css_values():
    with pytest.raises(ValueError):
        ConfiguracionAsistente(color_principal="red;position:fixed")


def test_assistant_icon_is_embedded_and_missing_icon_uses_fallback(monkeypatch, tmp_path):
    assert ui._leer_icono().startswith("data:image/webp;base64,")
    config = replace(CONFIGURACION, icono_ruta=str(tmp_path / "missing.png"))
    monkeypatch.setattr(ui, "CONFIGURACION", config)
    assert ui._leer_icono() is None


def test_enviar_pregunta_uses_direct_line(monkeypatch):
    configuracion = conexion._ConfiguracionDirectLine(
        endpoint="https://directline.example",
        secreto="secreto-de-prueba",
    )
    estado = {}
    solicitudes = []

    def solicitar(config, metodo, ruta, credencial, contenido=None, parametros=None):
        solicitudes.append((metodo, ruta, credencial, contenido, parametros))
        if ruta == "/conversations":
            return {
                "conversationId": "conversacion-1",
                "token": "token-de-prueba",
                "expires_in": 1800,
            }
        if ruta.endswith("/activities") and metodo == "POST":
            return {"id": "actividad-usuario"}
        if ruta.endswith("/activities") and metodo == "GET":
            return {
                "activities": [
                    {
                        "type": "message",
                        "from": {"id": "bot"},
                        "text": "Respuesta del agente",
                    }
                ],
                "watermark": "1",
            }
        raise AssertionError(f"Solicitud inesperada: {metodo} {ruta}")

    monkeypatch.setattr(conexion, "_leer_configuracion", lambda: configuracion)
    monkeypatch.setattr(conexion, "_solicitar_json", solicitar)
    monkeypatch.setattr(conexion.st, "session_state", estado)

    respuesta = conexion.enviar_pregunta("¿Qué haces?")

    assert respuesta == "Respuesta del agente"
    assert "¿Qué haces?" in solicitudes[1][3]["text"]
    assert solicitudes[0][2] == "secreto-de-prueba"
    assert estado["asistente_direct_line"]["conversation_id"] == "conversacion-1"


def test_direct_line_request_sends_authorization_and_uses_server_endpoint(monkeypatch):
    configuracion = conexion._ConfiguracionDirectLine(
        endpoint="https://directline.example",
        secreto="secreto-de-prueba",
    )
    solicitud = {}

    class Respuesta:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True}

    def solicitar(sesion, metodo, url, **kwargs):
        solicitud.update(metodo=metodo, url=url, **kwargs)
        return Respuesta()

    monkeypatch.setattr(conexion.requests.Session, "request", solicitar)
    resultado = conexion._solicitar_json(
        configuracion,
        "GET",
        "/conversations",
        "token-de-prueba",
    )

    assert resultado == {"ok": True}
    assert solicitud["url"] == "https://directline.example/v3/directline/conversations"
    assert solicitud["headers"]["Authorization"] == "Bearer token-de-prueba"


def test_direct_line_system_trust_adapter_keeps_tls_verification_enabled():
    adapter = SystemTrustStoreAdapter()

    assert adapter._ssl_context.verify_mode == ssl.CERT_REQUIRED
    assert adapter._ssl_context.check_hostname is True


def test_enviar_pregunta_handles_empty_text():
    assert conexion.enviar_pregunta("  ") == "Escribe una pregunta para que pueda ayudarte."


def test_enviar_pregunta_requires_direct_line_configuration(monkeypatch):
    monkeypatch.setattr(
        conexion,
        "_leer_configuracion",
        lambda: (_ for _ in ()).throw(conexion._ErrorConfiguracionDirectLine()),
    )
    assert "no está configurado" in conexion.enviar_pregunta("ayuda")


def test_enviar_pregunta_handles_direct_line_failure(monkeypatch):
    monkeypatch.setattr(
        conexion,
        "_leer_configuracion",
        lambda: conexion._ConfiguracionDirectLine(
            endpoint="https://directline.example",
            secreto="secreto-de-prueba",
        ),
    )
    monkeypatch.setattr(
        conexion,
        "_obtener_conversacion",
        lambda config: (_ for _ in ()).throw(conexion._ErrorDirectLine("fallo simulado")),
    )
    monkeypatch.setattr(conexion.st, "session_state", {})
    assert "No pude comunicarme" in conexion.enviar_pregunta("ayuda")


def test_reiniciar_conversacion_clears_remote_session(monkeypatch):
    estado = {"asistente_direct_line": {"conversation_id": "conversacion-1"}}
    monkeypatch.setattr(conexion.st, "session_state", estado)
    conexion.reiniciar_conversacion()
    assert "asistente_direct_line" not in estado


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
    assert len(opened.text_input) == 1
    assert any(button.key == "asistente-enviar" for button in opened.button)
    assert any(button.key == "asistente-agente-copilot-studio" for button in opened.button)
    assert any(button.key == "asistente-agente-gemini" for button in opened.button)
    assert any(button.label == "Giru" for button in opened.button)


def test_selected_provider_persists_after_chat_submission(monkeypatch):
    providers = []

    def responder(proveedor, pregunta, contexto, historial):
        providers.append(proveedor)
        return ui.Respuesta(f"Respuesta de {proveedor}")

    monkeypatch.setattr(
        ui,
        "enviar_pregunta",
        responder,
    )
    app = AppTest.from_string(
        "from asistente.ui import mostrar_asistente\nmostrar_asistente()"
    ).run()
    app.button[0].click().run()
    next(
        button for button in app.button
        if button.key == "asistente-agente-gemini"
    ).click().run()
    assert app.session_state["asistente_proveedor"] == "Gemini"
    assert any(
        element.value == "Responderá: **Giru**"
        for element in app.markdown
    )
    app.text_input[0].set_value("Pregunta de prueba")
    next(button for button in app.button if button.key == "asistente-enviar").click().run()

    assert not app.exception
    assert app.session_state["asistente_proveedor"] == "Gemini"
    assert any(
        element.value == "Responderá: **Giru**"
        for element in app.markdown
    )
    assert any(button.key == "asistente-enviar" for button in app.button)
    app.text_input[0].set_value("Pregunta de seguimiento")
    next(button for button in app.button if button.key == "asistente-enviar").click().run()

    assert not app.exception
    assert app.session_state["asistente_proveedor"] == "Gemini"
    assert providers == ["Gemini", "Gemini"]
    assert any(field.key == ui._PREGUNTA_KEY for field in app.text_input)
    assert any(button.key == "asistente-enviar" for button in app.button)


def test_composer_remains_after_sourced_gemini_answers(monkeypatch):
    source = SimpleNamespace(
        titulo="manual.md",
        url="https://example.com/manual.md",
    )
    provider_calls = []

    def answer_with_source(*args, **kwargs):
        provider_calls.append(args)
        return ui.Respuesta(
            "Respuesta respaldada por el documento [1].",
            (source,),
        )

    monkeypatch.setattr(ui, "enviar_pregunta", answer_with_source)
    app = AppTest.from_string(
        "from asistente.ui import mostrar_asistente\nmostrar_asistente()"
    ).run()
    app.button[0].click().run()
    next(
        button for button in app.button
        if button.key == "asistente-agente-gemini"
    ).click().run()
    app.text_input[0].set_value("Consulta con fuentes")
    app = next(button for button in app.button if button.key == "asistente-enviar").click().run()

    assert not app.exception
    assert any(field.key == ui._PREGUNTA_KEY for field in app.text_input)
    assert any(button.key == "asistente-enviar" for button in app.button)
    assert any("Consulta con fuentes" in element.value for element in app.text)

    app.text_input[0].set_value("Contrapregunta con fuentes")
    app = next(button for button in app.button if button.key == "asistente-enviar").click().run()

    assert not app.exception
    assert len(provider_calls) == 2
    assert any(field.key == ui._PREGUNTA_KEY for field in app.text_input)
    assert any(button.key == "asistente-enviar" for button in app.button)


def test_giru_process_command_requires_confirmation_and_does_not_call_provider(monkeypatch):
    provider_calls = []
    monkeypatch.setattr(
        ui,
        "enviar_pregunta",
        lambda *args, **kwargs: provider_calls.append(args),
    )
    app = AppTest.from_string(
        "from asistente.ui import mostrar_asistente\n"
        "mostrar_asistente('2026-10')"
    ).run()
    app.button[0].click().run()
    next(
        button for button in app.button
        if button.key == "asistente-agente-gemini"
    ).click().run()
    app.text_input[0].set_value("Actualízame las rentabilidades, por favor.")
    app = next(
        button for button in app.button
        if button.key == "asistente-enviar"
    ).click().run()

    assert not app.exception
    assert provider_calls == []
    assert any(
        "Entendí que solicitas" in element.value
        for element in app.text
    )
    assert any(
        button.label == "Confirmar solicitud"
        for button in app.button
    )
    assert (
        app.session_state["ccr_pending_process_operation"]["operation_id"]
        == "rentabilidades.actualizar"
    )

    app = next(
        button for button in app.button
        if button.label == "Confirmar solicitud"
    ).click().run()

    assert not app.exception
    assert provider_calls == []
    assert "ccr_pending_process_operation" not in app.session_state
    assert any(
        "no se ejecutó ninguna acción" in element.value
        for element in app.text
    )


def test_copilot_keeps_its_existing_route_for_process_commands(monkeypatch):
    provider_calls = []
    monkeypatch.setattr(
        ui,
        "enviar_pregunta",
        lambda *args, **kwargs: (
            provider_calls.append(args) or "Respuesta de Copilot"
        ),
    )
    app = AppTest.from_string(
        "from asistente.ui import mostrar_asistente\n"
        "mostrar_asistente('2026-10')"
    ).run()
    app.button[0].click().run()
    app.text_input[0].set_value("actualiza las rentabilidades")
    app = next(
        button for button in app.button
        if button.key == "asistente-enviar"
    ).click().run()

    assert not app.exception
    assert len(provider_calls) == 1
    assert provider_calls[0][0] == "Copilot Studio"
    assert "ccr_pending_process_operation" not in app.session_state


def test_question_is_rendered_while_provider_is_still_processing(monkeypatch):
    def keep_waiting(*args, **kwargs):
        ui.st.stop()

    monkeypatch.setattr(ui, "enviar_pregunta", keep_waiting)
    app = AppTest.from_string(
        "from asistente.ui import mostrar_asistente\nmostrar_asistente()"
    ).run()
    app.button[0].click().run()
    app.text_input[0].set_value("Pregunta que debe verse de inmediato")
    app = next(button for button in app.button if button.key == "asistente-enviar").click().run()

    assert not app.exception
    assert any(
        element.value == "Pregunta que debe verse de inmediato"
        for element in app.text
    )
