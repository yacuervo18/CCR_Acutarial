import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ts_generadas as ts  # noqa: E402


def make_run(root: Path, folder: str, reserve: str, tipo: str, period: str, **overrides):
    consolidated = root / folder / period / "6_Ts_consolidadas"
    consolidated.mkdir(parents=True)
    stock = consolidated / f"{period}_t_consolidada_Stock_{reserve}.csv"
    new = consolidated / f"{period}_t_consolidada_Nuevo_{reserve}.csv"
    stock.write_text("A;B\n", encoding="utf-8")
    new.write_text("A;B\n1;2\n", encoding="utf-8")
    manifest = {
        "version": 1,
        "tipo_ramo": tipo,
        "periodo": period,
        "fecha_valoracion_t": f"{period[:4]}-{period[4:]}-30",
        "fecha_valoracion_t_1": f"{period[:4]}-{int(period[4:]) - 1:02d}-28",
        "inflacion": 5.1,
        "smmlv": 1750905,
        "codificacion": "latin-1" if reserve == "Ley100" else "utf-8",
        "estado": "completo",
        "filas_stock": 0,
        "filas_nuevo": 1,
        "archivo_stock": stock.name,
        "archivo_nuevo": new.name,
        "actualizado_en": "2026-10-22T10:00:00-05:00",
    }
    manifest.update(overrides)
    (consolidated / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return consolidated


def test_reads_valid_generation(tmp_path):
    make_run(tmp_path, "Ley100", "Ley100", "LEY100", "202609")
    result = ts.latest_generation("Ley100", tmp_path)
    assert result is not None
    assert result.period == "202609"
    assert result.inflation == 5.1
    assert result.new_rows == 1
    assert result.stock_path.name == "202609_t_consolidada_Stock_Ley100.csv"


def test_latest_is_most_recent_valid_month(tmp_path):
    make_run(tmp_path, "ARL", "RM", "ARL", "202608")
    make_run(tmp_path, "ARL", "RM", "ARL", "202609")
    assert [g.period for g in ts.list_generations("RM", tmp_path)] == ["202609", "202608"]
    assert ts.find_generation("RM", "202608", tmp_path).period == "202608"
    assert ts.find_generation("RM", "202610", tmp_path) is None


def test_branches_do_not_mix(tmp_path):
    make_run(tmp_path, "ARL", "RM", "ARL", "202609")
    assert ts.latest_generation("Ley100", tmp_path) is None
    assert ts.latest_generation("Desconocido", tmp_path) is None


def test_rejects_generation_with_wrong_encoding(tmp_path):
    make_run(
        tmp_path,
        "ARL",
        "RM",
        "ARL",
        "202609",
        codificacion="latin-1",
    )
    assert ts.find_generation("RM", "202609", tmp_path) is None


def test_ignores_incomplete_or_inconsistent_generations(tmp_path):
    make_run(tmp_path, "Ley100", "Ley100", "LEY100", "202607", estado="consolidado_total")
    make_run(tmp_path, "Ley100", "Ley100", "LEY100", "202608", tipo_ramo="ARL")
    make_run(tmp_path, "Ley100", "Ley100", "LEY100", "202609", inflacion="5.1")
    make_run(tmp_path, "Ley100", "Ley100", "LEY100", "202610", fecha_valoracion_t="no-es-fecha")
    consolidated = make_run(tmp_path, "Ley100", "Ley100", "LEY100", "202611")
    (consolidated / "202611_t_consolidada_Nuevo_Ley100.csv").unlink()
    assert ts.list_generations("Ley100", tmp_path) == []


def test_damaged_manifest_is_ignored(tmp_path):
    consolidated = make_run(tmp_path, "Ley100", "Ley100", "LEY100", "202609")
    (consolidated / "manifest.json").write_text("{dañado", encoding="utf-8")
    assert ts.latest_generation("Ley100", tmp_path) is None


def test_missing_generator_folder_returns_nothing(tmp_path):
    assert ts.list_generations("Ley100", tmp_path / "no_existe") == []


def test_reader_does_not_modify_files(tmp_path):
    consolidated = make_run(tmp_path, "Ley100", "Ley100", "LEY100", "202609")
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in consolidated.iterdir()}
    ts.list_generations("Ley100", tmp_path)
    after = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in consolidated.iterdir()}
    assert before == after
