import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from src.ui import stock_generator


class FakeInput:
    def __init__(self):
        self.value = ""
        self.closed = False

    def write(self, value):
        self.value += value

    def close(self):
        self.closed = True

    def getvalue(self):
        return self.value


def test_branch_defaults_keep_ramo_and_company_separate(tmp_path):
    legacy = tmp_path / "params.json"
    legacy.write_text(
        json.dumps(
            {
                "fecha_valoracion": "2026-08-31",
                "fecha_minima_prod_nueva": "202301",
                "inflacion": 6.03,
                "smmlv": 1750905.0,
                "interes_real": 4.0,
                "ramo": "094",
                "compania": "22",
            }
        ),
        encoding="utf-8",
    )

    arl = stock_generator.load_branch_params("rm_arl", legacy)
    ley100 = stock_generator.load_branch_params("rm_ley_100", legacy)

    assert (arl["ramo"], arl["compania"]) == ("094", "22")
    assert (ley100["ramo"], ley100["compania"]) == ("087", "02")
    assert ley100["fecha_minima_prod_nueva"] == "202408"
    assert ley100["fecha_corte_vigencia"] == "2024-08-01"
    assert ley100["inflacion"] == 6.03


def test_saving_branch_parameters_does_not_persist_credentials(tmp_path):
    config_path = tmp_path / "params.json"
    values = {
        "fecha_valoracion": "2026-10-31",
        "fecha_minima_prod_nueva": "202408",
        "inflacion": 6.03,
        "smmlv": 1750905.0,
        "interes_real": 4.0,
        "fecha_corte_vigencia": "2024-08-01",
        "stock_vacia": False,
        "nuevo_vacia": False,
        "ramo": "087",
        "compania": "02",
        "usuario_osiris": "do-not-save-user",
        "contrasena_osiris": "do-not-save-password",
        "contrasena_macro": "do-not-save-macro-password",
    }

    stock_generator.save_branch_params("rm_ley_100", values, config_path)
    saved_text = config_path.read_text(encoding="utf-8")
    saved = json.loads(saved_text)

    assert saved["ramo_activo"] == "LEY100"
    assert saved["LEY100"]["ramo"] == "087"
    assert saved["LEY100"]["compania"] == "02"
    assert "do-not-save" not in saved_text
    assert "credentials" not in saved_text


def test_start_generator_sends_credentials_only_over_stdin(monkeypatch, tmp_path):
    class FakeProcess:
        def __init__(self):
            self.stdin = FakeInput()

        def poll(self):
            return None

    process = FakeProcess()
    captured = {}

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return process

    monkeypatch.setattr(stock_generator, "GENERATOR_PYTHON", tmp_path / "python.exe")
    monkeypatch.setattr(stock_generator, "GENERATOR_ROOT", tmp_path)
    monkeypatch.setattr(stock_generator, "RUN_LOGS", tmp_path / "run_logs")
    monkeypatch.setattr(stock_generator.subprocess, "Popen", fake_popen)
    (tmp_path / "python.exe").touch()
    payload = {
        "tipo_ramo": "ARL",
        "params": {"fecha_valoracion": "2026-08-31"},
        "credentials": {
            "usuario_osiris": "private-user",
            "contrasena_osiris": "private-osiris-password",
            "contrasena_macro": "private-macro-password",
        },
    }

    job = stock_generator.start_generator(payload)

    assert job.process is process
    assert captured["args"] == [
        str(tmp_path / "python.exe"),
        "-m",
        "core.worker",
    ]
    assert all(secret not in " ".join(captured["args"]) for secret in payload["credentials"].values())
    assert captured["kwargs"]["stdin"] == stock_generator.subprocess.PIPE
    assert captured["kwargs"]["stdout"] is not stock_generator.subprocess.PIPE
    assert captured["kwargs"]["env"]["PYTHONIOENCODING"] == "utf-8"
    sent_payload = json.loads(process.stdin.getvalue())
    assert sent_payload["credentials"] == payload["credentials"]
    assert not any(
        secret in value
        for secret in payload["credentials"].values()
        for value in captured["kwargs"]["env"].values()
    )
    assert process.stdin.closed


def test_stock_generator_form_renders_without_starting_a_job():
    stock_generator._JOBS.clear()
    app = AppTest.from_string(
        "from src.ui.stock_generator import render_stock_generator\n"
        "render_stock_generator('rm_ley_100', False)"
    ).run(timeout=30)

    assert not app.exception
    assert [button.label for button in app.button] == ["Configurar generación"]

    app = app.button[0].click().run(timeout=30)

    assert not app.exception
    assert any(button.label == "Confirmar y generar" for button in app.button)
    assert "Revisar el consolidado total antes de partir Stock/Nuevo" in {
        widget.label for widget in app.checkbox
    }
    assert {widget.label for widget in app.text_input} == {
        "Usuario Osiris/SURA",
        "Contraseña Osiris/SURA",
        "Contraseña de la macro",
    }


def test_finished_job_can_be_dismissed_without_deleting_its_log(tmp_path, monkeypatch):
    class FinishedProcess:
        def poll(self):
            return 1

    log_path = tmp_path / "failed-run.jsonl"
    log_path.write_text(
        '{"type":"error","message":"No hay conexión VPN"}\n',
        encoding="utf-8",
    )
    job = stock_generator.GeneratorJob(
        FinishedProcess(),
        log_path,
        "ARL",
        "202610",
        {},
    )
    monkeypatch.setitem(stock_generator._JOBS, "ARL", job)
    app = AppTest.from_string(
        "from src.ui.stock_generator import _render_job_monitor_content\n"
        "_render_job_monitor_content('ARL')"
    ).run(timeout=30)

    assert not app.exception
    assert any("No hay conexión VPN" in item.value for item in app.error)
    assert any(button.label == "Descartar resultado anterior" for button in app.button)

    app = next(
        button for button in app.button if button.label == "Descartar resultado anterior"
    ).click().run(timeout=30)

    assert not app.exception
    assert not app.error
    assert "ARL" not in stock_generator._JOBS
    assert log_path.is_file()


def test_running_job_cannot_be_dismissed(tmp_path, monkeypatch):
    class RunningProcess:
        def poll(self):
            return None

    job = stock_generator.GeneratorJob(
        RunningProcess(),
        tmp_path / "running-run.jsonl",
        "ARL",
        "202610",
        {},
    )
    monkeypatch.setitem(stock_generator._JOBS, "ARL", job)
    app = AppTest.from_string(
        "from src.ui.stock_generator import _render_job_monitor_content\n"
        "_render_job_monitor_content('ARL')"
    ).run(timeout=30)

    assert not app.exception
    assert not any(button.label == "Descartar resultado anterior" for button in app.button)
    assert stock_generator._JOBS["ARL"] is job


def test_generated_files_are_offered_as_three_downloads(tmp_path):
    output_dir = tmp_path / "Ley100" / "202610" / "6_Ts_consolidadas"
    output_dir.mkdir(parents=True)
    for name in (
        "202610_t_consolidada_Ley100.csv",
        "202610_t_consolidada_Stock_Ley100.csv",
        "202610_t_consolidada_Nuevo_Ley100.csv",
    ):
        (output_dir / name).write_text("NMPOLIZA\nP1\n", encoding="latin-1")
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "a" * 32,
                "archivo_revisado": None,
                "cantidad_correcciones": 0,
                "filas_total": 1,
                "filas_stock": 1,
                "filas_nuevo": 0,
            },
        ),
        encoding="utf-8",
    )

    app = AppTest.from_string(
        "from pathlib import Path\n"
        "from src.ui import stock_generator\n"
        f"stock_generator.GENERATOR_ROOT = Path({str(tmp_path)!r})\n"
        "job = stock_generator.GeneratorJob(None, Path('run.jsonl'), "
        "'LEY100', '202610', {})\n"
        "stock_generator._render_generated_downloads(job, "
        "{'total': 'total.csv', 'stock': 'stock.csv', 'nuevo': 'nuevo.csv'})"
    ).run(timeout=30)

    assert not app.exception
    assert {button.label for button in app.get("download_button")} == {
        "Descargar Total",
        "Descargar Stock",
        "Descargar Nuevo",
    }


def test_policy_review_saves_a_run_scoped_copy_and_audit_record(tmp_path):
    run_id = "a" * 32
    output_dir = tmp_path / "Ley100" / "202610" / "6_Ts_consolidadas"
    output_dir.mkdir(parents=True)
    total_path = output_dir / "202610_t_consolidada_Ley100.csv"
    total_path.write_text(
        "NMPOLIZA;Asegurado;TASA\n001;7;1.2\n",
        encoding="latin-1",
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "archivo_revisado": None,
                "cantidad_correcciones": 0,
            }
        ),
        encoding="utf-8",
    )

    app = AppTest.from_string(
        "from pathlib import Path\n"
        "from src.ui import stock_generator\n"
        f"stock_generator.GENERATOR_ROOT = Path({str(tmp_path)!r})\n"
        "job = stock_generator.GeneratorJob(None, Path('run.jsonl'), "
        "'LEY100', '202610', {}, True)\n"
        "stock_generator._render_review_editor(job)"
    ).run(timeout=30)
    assert not app.exception

    app.text_input[0].set_value("001").run()
    next(button for button in app.button if button.label == "Buscar póliza").click().run()
    assert not app.exception
    assert any("Se encontraron 1 registro" in item.value for item in app.success)

    next(box for box in app.selectbox if box.label == "Campo que deseas corregir").select("TASA").run()
    next(widget for widget in app.text_input if widget.label == "Nuevo valor").set_value("1.25").run()
    next(
        button
        for button in app.button
        if button.label == "Guardar corrección para esta corrida"
    ).click().run()
    assert not app.exception

    reviewed_path = output_dir / f"202610_t_consolidada_Ley100_revisado_{run_id}.csv"
    audit_path = output_dir / f"202610_correcciones_{run_id}.jsonl"
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert "001;7;1.2" in total_path.read_text(encoding="latin-1")
    assert "001;7;1.25" in reviewed_path.read_text(encoding="latin-1")
    assert audit_path.exists()
    assert manifest["archivo_revisado"] == reviewed_path.name
    assert manifest["cantidad_correcciones"] == 1
