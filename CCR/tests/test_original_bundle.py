import json
import zipfile

from streamlit.testing.v1 import AppTest

from src.ui import stock_generator
from src.ui.original_bundle import create_original_bundle


def _make_bundle_inputs(tmp_path, stock_empty):
    period = "202610"
    run_id = "a" * 32
    output = tmp_path / "Ley100" / period / "6_Ts_consolidadas"
    source_ts = tmp_path / "Ley100" / period / "1_Ts_descargadas"
    macro_dir = tmp_path / "Ley100" / period / "5_Macro_consolidada"
    output.mkdir(parents=True)
    source_ts.mkdir(parents=True)
    macro_dir.mkdir(parents=True)

    names = {
        "total": f"{period}_t_consolidada_Ley100.csv",
        "stock": f"{period}_t_consolidada_Stock_Ley100.csv",
        "nuevo": f"{period}_t_consolidada_Nuevo_Ley100.csv",
        "full_stock": f"{period}_t_consolidada_Stock_completo_Ley100.csv",
        "macro": f"Macro_consolidacion_Ley100_{period}.xlsm",
    }
    (output / names["total"]).write_text("POLIZA;VALOR\nTOTAL;1\n", encoding="latin-1")
    (output / names["stock"]).write_text(
        "POLIZA;VALOR\n" if stock_empty else "POLIZA;VALOR\nSTOCK;1\n",
        encoding="latin-1",
    )
    (output / names["nuevo"]).write_text("POLIZA;VALOR\nNUEVO;1\n", encoding="latin-1")
    if stock_empty:
        (output / names["full_stock"]).write_text(
            "POLIZA;VALOR\nSTOCK;1\n", encoding="latin-1"
        )
    (macro_dir / names["macro"]).write_bytes(b"macro")
    for number in range(1, 12):
        (source_ts / f"T{number}.xlsx").write_bytes(f"T{number}".encode())

    manifest = {
        "estado": "completo",
        "run_id": run_id,
        "archivo_revisado": None,
        "stock_vacia": stock_empty,
        "archivo_stock_completo": names["full_stock"] if stock_empty else names["stock"],
    }
    return period, run_id, names, manifest


def test_package_contains_complete_outputs_macro_and_used_ts(tmp_path):
    period, run_id, names, manifest = _make_bundle_inputs(tmp_path, stock_empty=False)

    archive = create_original_bundle(tmp_path, "Ley100", period, "Ley100", manifest)

    assert archive.name == f"Ts_original_{period}_{run_id}.zip"
    with zipfile.ZipFile(archive) as bundle:
        members = set(bundle.namelist())
        assert f"Ts_original/{names['total']}" in members
        assert f"Ts_original/{names['stock']}" in members
        assert f"Ts_original/{names['nuevo']}" in members
        assert f"Ts_original/t_consolidada/{names['macro']}" in members
        assert all(f"Ts_original/t_consolidada/T{number}.xlsx" in members for number in range(1, 12))


def test_empty_operational_stock_keeps_full_evidence_and_motor_files(tmp_path):
    period, _run_id, names, manifest = _make_bundle_inputs(tmp_path, stock_empty=True)

    archive = create_original_bundle(tmp_path, "Ley100", period, "Ley100", manifest)

    with zipfile.ZipFile(archive) as bundle:
        full_stock = bundle.read(f"Ts_original/{names['stock']}").decode("latin-1")
        assert "STOCK;1" in full_stock
        assert not any("para_motor" in name for name in bundle.namelist())
        assert not any("correcciones" in name for name in bundle.namelist())


def test_package_uses_revised_total_as_consolidated_evidence(tmp_path):
    period, run_id, names, manifest = _make_bundle_inputs(tmp_path, stock_empty=False)
    output = tmp_path / "Ley100" / period / "6_Ts_consolidadas"
    revised_name = f"{period}_t_consolidada_Ley100_revisado_{run_id}.csv"
    (output / revised_name).write_text("POLIZA;VALOR\nREVISADO;2\n", encoding="latin-1")
    manifest["archivo_revisado"] = revised_name

    archive = create_original_bundle(tmp_path, "Ley100", period, "Ley100", manifest)

    with zipfile.ZipFile(archive) as bundle:
        archived_total = bundle.read(f"Ts_original/{names['total']}").decode("latin-1")
        members = set(bundle.namelist())
    assert "REVISADO;2" in archived_total
    assert revised_name not in members


def test_empty_stock_requires_registered_full_evidence(tmp_path):
    period, _run_id, _names, manifest = _make_bundle_inputs(tmp_path, stock_empty=True)
    manifest["archivo_stock_completo"] = None

    try:
        create_original_bundle(tmp_path, "Ley100", period, "Ley100", manifest)
    except ValueError as error:
        assert "Stock completo" in str(error)
    else:
        raise AssertionError("Expected missing full-stock evidence to be rejected")


def test_generator_ui_prepares_and_offers_the_package(tmp_path, monkeypatch):
    period, _run_id, _names, manifest = _make_bundle_inputs(tmp_path, stock_empty=False)
    output = tmp_path / "Ley100" / period / "6_Ts_consolidadas"
    manifest.update(
        {
            "filas_total": 2,
            "filas_stock": 1,
            "filas_nuevo": 1,
            "cantidad_correcciones": 0,
        }
    )
    (output / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(stock_generator, "GENERATOR_ROOT", tmp_path)

    app = AppTest.from_string(
        "from pathlib import Path\n"
        "from src.ui import stock_generator\n"
        "job = stock_generator.GeneratorJob(None, Path('run.jsonl'), "
        "'LEY100', '202610', {})\n"
        "stock_generator._render_generated_downloads(job, "
        "{'total': 'total.csv', 'stock': 'stock.csv', 'nuevo': 'nuevo.csv'})"
    ).run()

    assert not app.exception
    app.button[0].click().run()
    assert not app.exception
    assert any(
        button.label == "Descargar Ts_original (.zip)"
        for button in app.get("download_button")
    )
