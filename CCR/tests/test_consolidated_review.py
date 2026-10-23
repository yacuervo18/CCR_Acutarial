import json

import pytest

from src.ui.consolidated_review import (
    append_change_record,
    find_policy_rows,
    update_reviewed_cell,
)


def test_find_policy_rows_returns_exact_match_and_only_matches(tmp_path):
    source = tmp_path / "total.csv"
    source.write_text(
        "NMPOLIZA;Asegurado;TASA\n001;7;1.2\n0010;8;1.3\n001;9;1.4\n",
        encoding="latin-1",
    )

    headers, matches = find_policy_rows(source, "001")

    assert headers == ["NMPOLIZA", "Asegurado", "TASA"]
    assert [index for index, _ in matches] == [0, 2]
    assert [row["Asegurado"] for _, row in matches] == ["7", "9"]


def test_update_reviewed_cell_preserves_original_and_writes_copy(tmp_path):
    original = tmp_path / "total.csv"
    reviewed = tmp_path / "total_revisado.csv"
    original.write_text(
        "NMPOLIZA;Asegurado;NOMBRE;TASA\n001;7;Peña;1.2\n",
        encoding="latin-1",
    )

    previous = update_reviewed_cell(original, reviewed, 0, "TASA", "1.25")

    assert previous == "1.2"
    assert original.read_text(encoding="latin-1") == (
        "NMPOLIZA;Asegurado;NOMBRE;TASA\n001;7;Peña;1.2\n"
    )
    assert reviewed.read_text(encoding="latin-1") == (
        "NMPOLIZA;Asegurado;NOMBRE;TASA\n001;7;Peña;1.25\n"
    )


@pytest.mark.parametrize("column", ["NMPOLIZA", "Asegurado"])
def test_update_reviewed_cell_protects_identifiers(tmp_path, column):
    source = tmp_path / "total.csv"
    reviewed = tmp_path / "reviewed.csv"
    source.write_text("NMPOLIZA;Asegurado;TASA\n001;7;1.2\n", encoding="latin-1")

    with pytest.raises(ValueError, match="protegida"):
        update_reviewed_cell(source, reviewed, 0, column, "changed")

    assert not reviewed.exists()


def test_append_change_record_writes_json_lines(tmp_path):
    audit = tmp_path / "changes.jsonl"

    append_change_record(
        audit,
        {"poliza": "001", "columna": "TASA", "anterior": "1.2", "nuevo": "1.25"},
    )

    record = json.loads(audit.read_text(encoding="utf-8").strip())
    assert record["poliza"] == "001"
    assert record["nuevo"] == "1.25"
