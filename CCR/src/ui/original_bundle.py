"""Build the downloadable monthly Ts_original archive."""
from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any
from uuid import uuid4


def _period_file(directory: Path, name: str, label: str) -> Path:
    if Path(name).name != name:
        raise ValueError(f"El nombre del archivo {label} no es válido.")
    path = directory / name
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró el archivo {label}: {path}")
    return path


def create_original_bundle(
    generator_root: Path,
    ramo_folder: str,
    period: str,
    suffix: str,
    manifest: dict[str, Any],
) -> Path:
    """Package completed outputs and the exact persisted inputs without recalculating."""
    if manifest.get("estado") != "completo":
        raise ValueError("El paquete Ts_original solo está disponible tras generar Stock y Nuevo.")
    if not period.isdigit() or len(period) != 6:
        raise ValueError("El período del paquete no es válido.")
    run_id = manifest.get("run_id")
    if not isinstance(run_id, str) or len(run_id) != 32 or not run_id.isalnum():
        raise ValueError("El registro de generación no contiene un identificador válido.")
    if ramo_folder not in {"ARL", "Ley100"} or suffix not in {"RM", "Ley100"}:
        raise ValueError("El ramo del paquete no es válido.")
    if (ramo_folder, suffix) not in {("ARL", "RM"), ("Ley100", "Ley100")}:
        raise ValueError("La carpeta y el sufijo no corresponden al mismo ramo.")

    period_dir = generator_root / ramo_folder / period
    output_dir = period_dir / "6_Ts_consolidadas"
    input_dir = period_dir / ("1_Ts_descargadas" if ramo_folder == "Ley100" else "4_Ts_integridad")
    macro_dir = period_dir / "5_Macro_consolidada"

    total_name = f"{period}_t_consolidada_{suffix}.csv"
    stock_name = f"{period}_t_consolidada_Stock_{suffix}.csv"
    nuevo_name = f"{period}_t_consolidada_Nuevo_{suffix}.csv"
    registered_total = manifest.get("archivo_revisado")
    if registered_total is None:
        total_source = _period_file(output_dir, total_name, "consolidado total")
    else:
        expected_reviewed = f"{period}_t_consolidada_Ley100_revisado_{run_id}.csv"
        if ramo_folder != "Ley100" or registered_total != expected_reviewed:
            raise ValueError("El consolidado revisado no corresponde a la corrida activa.")
        total_source = _period_file(output_dir, registered_total, "consolidado revisado")

    stock_source = _period_file(output_dir, stock_name, "Stock")
    nuevo_source = _period_file(output_dir, nuevo_name, "Nuevo")
    stock_vacia = manifest.get("stock_vacia") is True
    stock_full_name = manifest.get("archivo_stock_completo")
    if stock_vacia:
        expected_full = f"{period}_t_consolidada_Stock_completo_{suffix}.csv"
        if stock_full_name != expected_full:
            raise ValueError("No está registrado el Stock completo para evidencia.")
        stock_full_source = _period_file(output_dir, stock_full_name, "Stock completo de evidencia")
    else:
        stock_full_source = stock_source

    macro_name = f"Macro_consolidacion_{'Ley100' if ramo_folder == 'Ley100' else 'ARL'}_{period}.xlsm"
    macro_source = _period_file(macro_dir, macro_name, "macro calculada")
    if ramo_folder == "Ley100" and manifest.get("cantidad_correcciones"):
        corrected = macro_dir / f"Macro_consolidacion_Ley100_{period}_con_correcciones_{run_id}.xlsm"
        if corrected.is_file():
            macro_source = corrected
    ts_sources = [
        _period_file(input_dir, f"T{number}.xlsx", f"T{number}")
        for number in range(1, 12)
    ]

    archive = output_dir / f"Ts_original_{period}_{run_id}.zip"
    archive.parent.mkdir(parents=True, exist_ok=True)
    temporary = archive.with_name(f".{archive.name}.{uuid4().hex}.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", allowZip64=True) as bundle:
            root = "Ts_original"
            bundle.write(total_source, f"{root}/{total_name}", compress_type=zipfile.ZIP_DEFLATED)
            bundle.write(stock_full_source, f"{root}/{stock_name}", compress_type=zipfile.ZIP_DEFLATED)
            bundle.write(nuevo_source, f"{root}/{nuevo_name}", compress_type=zipfile.ZIP_DEFLATED)

            archive_input_dir = f"{root}/t_consolidada"
            bundle.write(
                macro_source,
                f"{archive_input_dir}/{macro_name}",
                compress_type=zipfile.ZIP_STORED,
            )
            for source in ts_sources:
                bundle.write(
                    source,
                    f"{archive_input_dir}/{source.name}",
                    compress_type=zipfile.ZIP_STORED,
                )
        temporary.replace(archive)
    finally:
        if temporary.exists():
            temporary.unlink()
    return archive
