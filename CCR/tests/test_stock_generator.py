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
        "render_stock_generator('rm_arl', False)"
    ).run(timeout=30)

    assert not app.exception
    assert [button.label for button in app.button] == ["Configurar generación"]

    app = app.button[0].click().run(timeout=30)

    assert not app.exception
    assert any(button.label == "Confirmar y generar" for button in app.button)
    assert {widget.label for widget in app.text_input} == {
        "Usuario Osiris/SURA",
        "Contraseña Osiris/SURA",
        "Contraseña de la macro",
    }
