import pytest

from src.phase1.process_operation_contract import (
    PROCESS_OPERATION_HANDLERS,
    ejecutar_operacion_confirmada,
    registrar_manejador_operacion,
    reconocer_operacion,
)


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("Actualízame las rentabilidades, por favor.", "rentabilidades.actualizar"),
        ("Copiar la tabla de rentabilidades", "rentabilidades.copiar"),
        ("Extraer datos", "indices.extraer"),
        ("Extraer datos de índices", "indices.extraer"),
        ("Actualizar OSIRIS", "indices.actualizar_osiris"),
        ("Actualizar archivos", "indices.actualizar_archivos"),
    ],
)
def test_explicit_process_commands_map_to_stable_operation_ids(command, expected):
    operation = reconocer_operacion(command)

    assert operation is not None
    assert operation.identifier == expected


@pytest.mark.parametrize(
    "question",
    [
        "¿Cómo se actualizan las rentabilidades?",
        "¿Qué significa actualizar OSIRIS?",
    ],
)
def test_questions_and_ambiguous_phrases_are_not_treated_as_commands(question):
    assert reconocer_operacion(question) is None


def test_confirmed_operation_without_handler_reports_unavailable_without_execution(monkeypatch):
    identifier = "rentabilidades.actualizar"
    monkeypatch.delitem(PROCESS_OPERATION_HANDLERS, identifier, raising=False)
    result = ejecutar_operacion_confirmada(identifier, "2026-10")

    assert result.status == "unavailable"
    assert "no se ejecutó" in result.message


def test_osiris_dispatch_cannot_run_without_data_review_even_with_a_handler(monkeypatch):
    dispatched = []
    monkeypatch.setitem(
        PROCESS_OPERATION_HANDLERS,
        "indices.actualizar_osiris",
        lambda period: dispatched.append(period) or "No debe ejecutarse",
    )

    result = ejecutar_operacion_confirmada(
        "indices.actualizar_osiris",
        "2026-10",
    )

    assert result.status == "unavailable"
    assert "confirmación adicional" in result.message
    assert dispatched == []


def test_file_update_cannot_register_a_handler_before_permissions_are_ready():
    with pytest.raises(ValueError, match="permisos"):
        registrar_manejador_operacion(
            "indices.actualizar_archivos",
            lambda period: "No debe estar habilitado",
        )

    assert "indices.actualizar_archivos" not in PROCESS_OPERATION_HANDLERS
