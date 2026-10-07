from datetime import date, timedelta

import pytest

from src.phase1.domain import EstadoProceso, Tarea, derivar_estado, porcentaje_global, ResumenProceso
from src.phase1.notifications import validar_destinatarios
from src.phase1.repository import Repository
from src.phase1.service import ProcessService


def test_state_derivation_covers_priority_rules():
    tasks = (Tarea(1, "Uno"), Tarea(2, "Dos", True))
    assert derivar_estado(tasks, bloqueado=True) == EstadoProceso.BLOQUEADO
    assert derivar_estado((Tarea(1, "Uno", True),)) == EstadoProceso.COMPLETADO
    assert derivar_estado(tasks, date.today() - timedelta(days=1)) == EstadoProceso.VENCIDO
    assert derivar_estado(tasks) == EstadoProceso.EN_PROCESO


def test_global_percentage_and_kpis_use_persisted_state(tmp_path):
    repository = Repository(tmp_path / "ccr.db")
    service = ProcessService(repository)
    summaries = service.summaries("2026-10")
    assert porcentaje_global(summaries) == 0
    repository.set_task("2026-10", "rentabilidades", 1, True)
    dashboard = service.dashboard("2026-10")
    assert dashboard["avance"] > 0
    assert dashboard["kpis"]["pending"] < sum(s.total for s in summaries)


def test_periods_are_independent_and_history_is_kept(tmp_path):
    repository = Repository(tmp_path / "ccr.db")
    service = ProcessService(repository)
    repository.set_task("2026-10", "f394", 1, True)
    assert service.summaries("2026-11")[2].completadas == 0
    assert service.summaries("2026-10")[2].completadas == 1
    assert set(repository.periods()) == {"2026-10", "2026-11"}


def test_email_validation():
    assert validar_destinatarios("uno@empresa.com, dos@empresa.co")[1] == "dos@empresa.co"
    with pytest.raises(ValueError):
        validar_destinatarios("no-es-correo")
