from types import SimpleNamespace

from asistente import github_gemini, router


def test_missing_gemini_settings_identify_the_section_without_exposing_values(monkeypatch):
    monkeypatch.setattr(
        github_gemini,
        "st",
        SimpleNamespace(
            secrets={
                "github_knowledge": {
                    "repository": "example/manuales",
                    "branch": "main",
                    "documents_path": ".",
                    "read_token": "github-read-only-test",
                }
            }
        ),
    )

    result = github_gemini.responder("¿Qué documentos hay?")

    assert "[gemini]" in result.texto
    assert "entorno activo de CCR" in result.texto
    assert "github-read-only-test" not in result.texto


def test_github_headers_use_the_configured_read_token():
    configuracion = github_gemini._Configuracion(
        repositorio="example/manuales",
        rama="main",
        carpeta=".",
        token_github="github-read-only-test",
        clave_gemini="gemini-test",
        modelo_gemini="gemini-test-model",
    )

    headers = github_gemini._github_headers(configuracion)
    raw_headers = github_gemini._github_headers(configuracion, raw=True)

    assert headers["Authorization"] == "Bearer github-read-only-test"
    assert headers["Accept"] == "application/vnd.github+json"
    assert raw_headers["Accept"] == "application/vnd.github.raw+json"


def test_document_search_prefers_fragment_matching_question():
    fragments = [
        github_gemini._Fragmento(
            "Para realizar la convocatoria, enviar el orden del día.",
            "Comité",
            "comites.txt",
            "https://github.com/example/docs/blob/main/comites.txt",
        ),
        github_gemini._Fragmento(
            "Actualizar la curva con las tasas publicadas.",
            "Rentabilidades",
            "rentabilidades.txt",
            "https://github.com/example/docs/blob/main/rentabilidades.txt",
        ),
    ]

    results = github_gemini._buscar_fragmentos(
        "¿Cómo preparo la convocatoria del comité?",
        fragments,
    )

    assert results == [fragments[0]]


def test_empty_repository_does_not_call_gemini(monkeypatch):
    configuracion = github_gemini._Configuracion(
        repositorio="example/manuales",
        rama="main",
        carpeta=".",
        token_github="github-read-only-test",
        clave_gemini="gemini-test",
        modelo_gemini="gemini-test-model",
    )
    monkeypatch.setattr(github_gemini, "_leer_configuracion", lambda: configuracion)
    monkeypatch.setattr(github_gemini, "_cargar_fragmentos", lambda _: [])
    monkeypatch.setattr(
        github_gemini,
        "_generar_respuesta",
        lambda *args: (_ for _ in ()).throw(AssertionError("Gemini no debe invocarse")),
    )

    result = github_gemini.responder("¿Cómo se prepara el comité?")

    assert "Aún no hay documentos" in result.texto
    assert not result.fuentes


def test_gemini_request_keeps_api_key_in_header_and_returns_sources(monkeypatch):
    configuracion = github_gemini._Configuracion(
        repositorio="example/manuales",
        rama="main",
        carpeta=".",
        token_github="github-read-only-test",
        clave_gemini="gemini-key-test",
        modelo_gemini="gemini-test-model",
    )
    fragment = github_gemini._Fragmento(
        "Convocar el comité siguiendo estos pasos.",
        "Convocatoria",
        "comites.txt",
        "https://github.com/example/manuales/blob/main/comites.txt",
    )
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "Envía la convocatoria [1]."}]
                        }
                    }
                ]
            }

    def post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return Response()

    monkeypatch.setattr(github_gemini.requests, "post", post)
    monkeypatch.setattr(
        github_gemini,
        "_leer_configuracion",
        lambda: configuracion,
    )
    monkeypatch.setattr(github_gemini, "_cargar_fragmentos", lambda _: [fragment])

    result = github_gemini.responder("¿Cómo convoco el comité?")

    assert result.texto == "Envía la convocatoria [1]."
    assert result.fuentes[0].url == fragment.url
    assert captured["headers"]["x-goog-api-key"] == "gemini-key-test"
    assert "gemini-key-test" not in captured["url"]
    assert "Convocar el comité" in captured["json"]["contents"][-1]["parts"][0]["text"]


def test_copilot_authentication_error_shows_expected_message_without_fallback(monkeypatch):
    gemini_called = False

    def fake_gemini(*args, **kwargs):
        nonlocal gemini_called
        gemini_called = True
        raise AssertionError("No debe usarse Gemini como fallback")

    monkeypatch.setattr(
        router.conexion,
        "enviar_pregunta",
        lambda *args: "Error: IntegratedAuthenticationNotSupportedInChannel",
    )
    monkeypatch.setattr(router, "responder", fake_gemini)

    answer = router.enviar_pregunta("Copilot Studio", "Ayuda")

    assert answer == (
        "Aún no tenemos los permisos para utilizar Microsoft 365 Copilot, pero no te "
        "preocupes: haz clic en Agente y cambia a Giru. Giru es un agente diseñado y "
        "desarrollado para ayudarte a gestionar tareas del área."
    )
    assert gemini_called is False


def test_provider_router_dispatches_to_gemini_only_when_selected(monkeypatch):
    expected = github_gemini.Respuesta("Respuesta basada en documentos")
    calls = []
    monkeypatch.setattr(
        router,
        "responder",
        lambda question, context, history: calls.append((question, context, history)) or expected,
    )

    result = router.enviar_pregunta(
        "Gemini",
        "Pregunta",
        {"ultimo_error": {"tipo": "ValueError"}},
        [{"role": "user", "content": "Anterior"}],
    )

    assert result is expected
    assert calls == [
        (
            "Pregunta",
            {"ultimo_error": {"tipo": "ValueError"}},
            [{"role": "user", "content": "Anterior"}],
        )
    ]
