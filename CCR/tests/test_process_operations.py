from streamlit.testing.v1 import AppTest

from src.phase1.process_operation_contract import PROCESS_OPERATION_HANDLERS


def render_operations(code: str, readonly: bool = False, period: str = "2026-10"):
    return AppTest.from_string(
        "from src.ui.process_operations import render_process_operations\n"
        f"render_process_operations({code!r}, {readonly!r}, {period!r})"
    ).run()


def test_rentabilidades_actions_request_confirmation_without_running():
    app = render_operations("rentabilidades")

    assert not app.exception
    assert [button.label for button in app.button] == [
        "Actualizar rentabilidades",
        "Copiar",
    ]
    assert not any(button.disabled for button in app.button)

    app.button[0].click().run()
    pending = app.session_state["ccr_pending_process_operation"]
    assert pending["operation_id"] == "rentabilidades.actualizar"
    assert pending["period"] == "2026-10"
    assert any("Confirmar solicitud" == button.label for button in app.button)
    assert any("no iniciará scraping" in element.value for element in app.warning)

    confirm = next(button for button in app.button if button.label == "Confirmar solicitud")
    app = confirm.click().run()

    assert not app.exception
    assert any("no se ejecutó ninguna acción" in element.value for element in app.info)
    assert "ccr_pending_process_operation" not in app.session_state


def test_indices_actions_require_confirmation_and_files_remain_disabled():
    app = render_operations("indices")

    assert not app.exception
    assert [button.label for button in app.button] == [
        "Extraer datos",
        "Actualizar OSIRIS",
        "Actualizar archivos",
    ]
    assert [button.disabled for button in app.button] == [False, False, True]
    assert "permisos" in app.button[2].help


def test_process_without_operation_panel_renders_no_controls():
    app = render_operations("f394")

    assert not app.exception
    assert not app.button


def test_historical_period_cannot_start_process_operation():
    app = render_operations("rentabilidades", readonly=True)

    assert not app.exception
    assert all(button.disabled for button in app.button)


def test_cancelling_a_process_request_does_not_dispatch_it(monkeypatch):
    dispatched = []
    monkeypatch.setitem(
        PROCESS_OPERATION_HANDLERS,
        "indices.extraer",
        lambda period: dispatched.append(period) or "Mock",
    )
    app = render_operations("indices")
    app.button[0].click().run()
    pending = app.session_state["ccr_pending_process_operation"]
    assert pending["operation_id"] == "indices.extraer"

    app = next(button for button in app.button if button.label == "Cancelar").click().run()

    assert not app.exception
    assert "ccr_pending_process_operation" not in app.session_state
    assert any("cancelada" in element.value for element in app.info)
    assert dispatched == []


def test_panel_dispatches_only_after_confirmation_with_the_requested_period(monkeypatch):
    dispatched = []
    monkeypatch.setitem(
        PROCESS_OPERATION_HANDLERS,
        "rentabilidades.actualizar",
        lambda period: dispatched.append(period) or f"Resultado simulado para {period}",
    )
    app = render_operations("rentabilidades", period="2026-11")
    app.button[0].click().run()

    assert dispatched == []
    app = next(
        button for button in app.button
        if button.label == "Confirmar solicitud"
    ).click().run()

    assert not app.exception
    assert dispatched == ["2026-11"]
    assert any("Resultado simulado para 2026-11" in element.value for element in app.info)
