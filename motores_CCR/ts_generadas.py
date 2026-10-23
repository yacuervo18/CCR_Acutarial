"""Lector de solo lectura de las Ts consolidadas que deja `generador_t`.

Es independiente: no importa codigo del generador ni de los motores, y nunca
escribe, mueve ni borra nada. Solo reconoce una generacion cuando su
manifest.json esta completo y coherente con los archivos en disco; si algo no
cuadra, esa generacion se ignora y el motor sigue funcionando con archivos
cargados a mano.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

GENERATOR_DIR = Path(__file__).resolve().parent.parent / "generador_t"

# reserva -> (carpeta del ramo, tipo_ramo del manifest, codificación requerida)
BRANCHES = {
    "Ley100": ("Ley100", "LEY100", "latin-1"),
    "RM": ("ARL", "ARL", "utf-8"),
}


@dataclass(frozen=True)
class GeneratedTs:
    period: str
    reserve: str
    valuation_date: date
    previous_valuation_date: date
    inflation: float
    smmlv: float
    stock_path: Path
    new_path: Path
    stock_rows: int
    new_rows: int
    generated_at: str
    corrections: int


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _count(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _read_generation(
    period_dir: Path,
    reserve: str,
    tipo_ramo: str,
    expected_encoding: str,
) -> GeneratedTs | None:
    consolidated = period_dir / "6_Ts_consolidadas"
    try:
        manifest = json.loads((consolidated / "manifest.json").read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            return None
        period = period_dir.name
        if (
            manifest.get("version") != 1
            or manifest.get("tipo_ramo") != tipo_ramo
            or manifest.get("periodo") != period
            or manifest.get("estado") != "completo"
            or manifest.get("codificacion") != expected_encoding
        ):
            return None

        valuation = date.fromisoformat(manifest["fecha_valoracion_t"])
        previous = date.fromisoformat(manifest["fecha_valoracion_t_1"])
        inflation = _number(manifest.get("inflacion"))
        smmlv = _number(manifest.get("smmlv"))
        stock_rows = _count(manifest.get("filas_stock"))
        new_rows = _count(manifest.get("filas_nuevo"))
        if (
            inflation is None
            or smmlv is None
            or stock_rows is None
            or new_rows is None
            or valuation.strftime("%Y%m") != period
            or previous >= valuation
        ):
            return None

        stock_path = consolidated / f"{period}_t_consolidada_Stock_{reserve}.csv"
        new_path = consolidated / f"{period}_t_consolidada_Nuevo_{reserve}.csv"
        if (
            manifest.get("archivo_stock") != stock_path.name
            or manifest.get("archivo_nuevo") != new_path.name
            or not stock_path.is_file()
            or not new_path.is_file()
            or stock_path.stat().st_size == 0
            or new_path.stat().st_size == 0
        ):
            return None

        return GeneratedTs(
            period=period,
            reserve=reserve,
            valuation_date=valuation,
            previous_valuation_date=previous,
            inflation=inflation,
            smmlv=smmlv,
            stock_path=stock_path,
            new_path=new_path,
            stock_rows=stock_rows,
            new_rows=new_rows,
            generated_at=str(manifest.get("actualizado_en") or ""),
            corrections=_count(manifest.get("cantidad_correcciones")) or 0,
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def list_generations(reserve: str, generator_dir: Path | None = None) -> list[GeneratedTs]:
    """Generaciones completas y validas del ramo, de la mas reciente a la mas antigua."""
    if reserve not in BRANCHES:
        return []
    folder_name, tipo_ramo, encoding = BRANCHES[reserve]
    branch_dir = (generator_dir or GENERATOR_DIR) / folder_name
    try:
        folders = [p for p in branch_dir.iterdir() if p.is_dir() and p.name.isdigit() and len(p.name) == 6]
    except OSError:
        return []
    found = (
        _read_generation(folder, reserve, tipo_ramo, encoding)
        for folder in sorted(folders, reverse=True)
    )
    return [item for item in found if item is not None]


def find_generation(reserve: str, period: str, generator_dir: Path | None = None) -> GeneratedTs | None:
    """Generacion valida de un mes concreto (YYYYMM), o None."""
    return next((g for g in list_generations(reserve, generator_dir) if g.period == period), None)


def latest_generation(reserve: str, generator_dir: Path | None = None) -> GeneratedTs | None:
    generations = list_generations(reserve, generator_dir)
    return generations[0] if generations else None
