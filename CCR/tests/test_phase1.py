from datetime import date, timedelta

import pytest

from src.phase1.domain import EstadoProceso, Tarea, derivar_estado, porcentaje_global, ResumenProceso
from datetime import datetime

from src.phase1.notifications import validar_destinatarios, parse_destinatarios
from src.phase1.repository import Repository
from src.phase1.service import ProcessService
from src.phase1.content import delete_videos, load_process_content, save_uploaded_video


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


def test_process_schedule_only_reminds_when_tasks_are_pending(tmp_path):
    repository = Repository(tmp_path / "ccr.db")
    service = ProcessService(repository)
    repository.save_process_schedule("f394", "2026-10-01", "08:00", [10], 1440, [{"label": "Carlos", "value": "carlos@empresa.com"}])
    reminders = service.daily_reminders("2026-10", datetime(2026, 10, 7, 9, 0))
    assert any(reminder.proceso == "f394" for reminder in reminders)
    for task_id in range(1, 6):
        repository.set_task("2026-10", "f394", task_id, True)
    assert not any(reminder.proceso == "f394" for reminder in service.daily_reminders("2026-10", datetime(2026, 10, 7, 9, 0)))


def test_recipient_lines_support_name_and_identifier():
    assert parse_destinatarios("Carlos | carlos@empresa.com\nCanal Reservas | canal-reservas")[1]["value"] == "canal-reservas"


def test_schedule_is_general_and_can_have_period_override(tmp_path):
    repository = Repository(tmp_path / "ccr.db")
    repository.save_process_schedule("f394", "2026-01-01", "08:00", list(range(1, 13)), 1440, [])
    repository.save_process_schedule("f394", "2026-10-15", "09:00", [10], 60, [], "2026-10")
    assert repository.process_schedule("f394", "2026-11")["scheduled_time"] == "08:00"
    assert repository.process_schedule("f394", "2026-10")["scheduled_time"] == "09:00"


def test_reset_only_clears_tasks_and_keeps_schedule(tmp_path):
    repository = Repository(tmp_path / "ccr.db")
    repository.set_task("2026-10", "f394", 1, True)
    repository.save_process_schedule("f394", "2026-01-01", "08:00", list(range(1, 13)), 1440, [])
    repository.reset_tasks("2026-10")
    assert repository.completed("2026-10", "f394") == set()
    assert repository.process_schedule("f394")["scheduled_time"] == "08:00"


def test_process_tasks_can_be_added_edited_and_deactivated(tmp_path):
    repository = Repository(tmp_path / "ccr.db")
    task_id = repository.add_process_task("f394", "Nueva tarea")
    assert any(row["name"] == "Nueva tarea" for row in repository.process_tasks("f394"))
    repository.update_process_task("f394", task_id, "Tarea renombrada", True, True)
    updated = next(row for row in repository.process_tasks("f394") if row["task_id"] == task_id)
    assert updated["name"] == "Tarea renombrada"
    assert updated["sox"] == 1
    repository.deactivate_process_task("f394", task_id)
    assert not any(row["task_id"] == task_id for row in repository.process_tasks("f394"))
    assert any(row["task_id"] == task_id for row in repository.process_tasks("f394", include_inactive=True))


def test_dynamic_task_catalog_updates_summary_counts(tmp_path):
    repository = Repository(tmp_path / "ccr.db")
    service = ProcessService(repository)
    before = next(summary for summary in service.summaries("2026-10") if summary.proceso.codigo == "f394")
    task_id = repository.add_process_task("f394", "Nueva tarea")
    after = next(summary for summary in service.summaries("2026-10") if summary.proceso.codigo == "f394")
    assert after.total == before.total + 1
    assert any(task.id == task_id and task.nombre == "Nueva tarea" for task in after.proceso.tareas)
    repository.deactivate_process_task("f394", task_id)
    final = next(summary for summary in service.summaries("2026-10") if summary.proceso.codigo == "f394")
    assert final.total == before.total


def test_process_content_is_persisted_separately_from_tasks(tmp_path):
    repository = Repository(tmp_path / "ccr.db")
    repository.save_process_content("f394", "Texto actualizado", "https://manual.example", "Observación")
    content = repository.process_content("f394")
    assert content["what_to_do"] == "Texto actualizado"
    assert content["manual_url"] == "https://manual.example"
    assert content["important_note"] == "Observación"
    assert repository.completed("2026-10", "f394") == set()


class UploadedVideo:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def getbuffer(self):
        return self._data


def test_video_upload_replaces_and_deletes_process_video(tmp_path, monkeypatch):
    import src.phase1.content as content_module

    monkeypatch.setattr(content_module, "CONTENT_ROOT", tmp_path / "content")
    (tmp_path / "content" / "f394" / "media").mkdir(parents=True)
    first = save_uploaded_video("f394", UploadedVideo("manual.mp4", b"first"))
    assert first.read_bytes() == b"first"
    second = save_uploaded_video("f394", UploadedVideo("updated.webm", b"second"))
    assert second.read_bytes() == b"second"
    assert not first.exists()
    assert load_process_content("f394", "fallback").video_path == second
    delete_videos("f394")
    assert not second.exists()


def test_video_upload_rejects_unsupported_extension(tmp_path, monkeypatch):
    import src.phase1.content as content_module

    monkeypatch.setattr(content_module, "CONTENT_ROOT", tmp_path / "content")
    with pytest.raises(ValueError, match="MP4"):
        save_uploaded_video("f394", UploadedVideo("manual.exe", b"data"))
