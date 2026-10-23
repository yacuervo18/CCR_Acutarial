"""Copia controlada de Ts generadas hacia la carpeta de entrada del motor."""
from __future__ import annotations

import shutil
from pathlib import Path

from ts_generadas import GeneratedTs

RESERVE_SUFFIXES = {"Ley100": "Ley100", "RM": "RM"}


def copy_generated_ts(generation: GeneratedTs, target_dir: Path) -> tuple[str, str]:
    """Copia Nuevo y Stock sin sobrescribir archivos existentes."""
    if generation.reserve not in RESERVE_SUFFIXES:
        raise ValueError(f"Ramo no soportado para importar Ts: {generation.reserve}.")

    sources = (generation.new_path, generation.stock_path)
    suffix = RESERVE_SUFFIXES[generation.reserve]
    names = (
        f"{generation.period}_t_consolidada_Nuevo_{suffix}.csv",
        f"{generation.period}_t_consolidada_Stock_{suffix}.csv",
    )
    if any(not source.is_file() for source in sources):
        raise FileNotFoundError("Falta uno de los archivos de la generación seleccionada.")

    target_dir.mkdir(parents=True, exist_ok=True)
    destinations = tuple(target_dir / name for name in names)
    existing = [path.name for path in destinations if path.exists()]
    if existing:
        raise FileExistsError(
            "No se copiaron las Ts porque ya existen archivos con esos nombres: "
            + ", ".join(existing)
            + ". Prepare el período y confirme el reemplazo antes de volver a intentar."
        )

    installed_paths: list[Path] = []
    try:
        for source, destination in zip(sources, destinations):
            with source.open("rb") as source_file, destination.open("xb") as target_file:
                installed_paths.append(destination)
                shutil.copyfileobj(source_file, target_file)
    except OSError:
        for installed in installed_paths:
            installed.unlink(missing_ok=True)
        raise

    return names
