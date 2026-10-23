import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ts_generadas import GeneratedTs  # noqa: E402
from ts_import import copy_generated_ts  # noqa: E402


def make_generation(tmp_path: Path, reserve: str = "Ley100") -> GeneratedTs:
    period = "202609"
    new_path = tmp_path / "new.csv"
    stock_path = tmp_path / "stock.csv"
    new_path.write_bytes(b"header\nnew-policy\n")
    stock_path.write_bytes(b"header\n")
    return GeneratedTs(
        period=period,
        reserve=reserve,
        valuation_date=date(2026, 9, 30),
        previous_valuation_date=date(2026, 8, 31),
        inflation=6.29,
        smmlv=1750905,
        stock_path=stock_path,
        new_path=new_path,
        stock_rows=0,
        new_rows=1,
        generated_at="2026-10-22T10:00:00-05:00",
        corrections=0,
    )


def test_copies_exact_names_and_contents(tmp_path):
    generation = make_generation(tmp_path)
    target = tmp_path / "inputs" / "202609" / "t_consolidada"
    names = copy_generated_ts(generation, target)

    assert names == (
        "202609_t_consolidada_Nuevo_Ley100.csv",
        "202609_t_consolidada_Stock_Ley100.csv",
    )
    assert (target / names[0]).read_bytes() == b"header\nnew-policy\n"
    assert (target / names[1]).read_bytes() == b"header\n"


def test_refuses_to_overwrite_existing_file(tmp_path):
    generation = make_generation(tmp_path)
    target = tmp_path / "t_consolidada"
    target.mkdir()
    existing = target / "202609_t_consolidada_Nuevo_Ley100.csv"
    existing.write_bytes(b"keep this file")

    with pytest.raises(FileExistsError, match="No se copiaron"):
        copy_generated_ts(generation, target)

    assert existing.read_bytes() == b"keep this file"
    assert not (target / "202609_t_consolidada_Stock_Ley100.csv").exists()


def test_copies_arl_files_with_rm_names(tmp_path):
    generation = make_generation(tmp_path, reserve="RM")
    target = tmp_path / "arl" / "t_consolidada"
    names = copy_generated_ts(generation, target)

    assert names == (
        "202609_t_consolidada_Nuevo_RM.csv",
        "202609_t_consolidada_Stock_RM.csv",
    )
    assert (target / names[0]).read_bytes() == b"header\nnew-policy\n"
    assert (target / names[1]).read_bytes() == b"header\n"


def test_rejects_unsupported_reserve(tmp_path):
    with pytest.raises(ValueError, match="Ramo no soportado"):
        copy_generated_ts(make_generation(tmp_path, reserve="Other"), tmp_path / "target")


def test_removes_partial_copy_if_second_file_fails(tmp_path, monkeypatch):
    generation = make_generation(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    original_open = Path.open

    def fail_stock_open(path, *args, **kwargs):
        if path.name.endswith("_Stock_Ley100.csv") and args and args[0] == "xb":
            raise OSError("simulated write failure")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_stock_open)
    with pytest.raises(OSError, match="simulated write failure"):
        copy_generated_ts(generation, target)
    assert list(target.iterdir()) == []
