"""CSV helpers for Ley 100 consolidated-policy review."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4


POLICY_COLUMN = "NMPOLIZA"
READ_ONLY_COLUMNS = {POLICY_COLUMN, "Asegurado"}


def find_policy_rows(
    source_path: Path, policy_number: str
) -> tuple[list[str], list[tuple[int, dict[str, str]]]]:
    """Search by exact policy number while keeping only matching rows in memory."""
    query = policy_number.strip()
    if not query:
        raise ValueError("Escribe un número de póliza para buscar.")

    matches: list[tuple[int, dict[str, str]]] = []
    with source_path.open("r", encoding="latin-1", newline="") as source:
        reader = csv.reader(source, delimiter=";")
        headers = next(reader, None)
        if not headers or POLICY_COLUMN not in headers:
            raise ValueError(f"El consolidado no contiene la columna requerida {POLICY_COLUMN}.")
        policy_index = headers.index(POLICY_COLUMN)
        for row_index, values in enumerate(reader):
            if len(values) != len(headers):
                raise ValueError(f"La fila {row_index + 2} tiene un número de columnas inválido.")
            if values[policy_index].strip() == query:
                matches.append((row_index, dict(zip(headers, values))))
    return headers, matches


def update_reviewed_cell(
    source_path: Path,
    reviewed_path: Path,
    row_index: int,
    column: str,
    new_value: str,
) -> str:
    """Write one cell into an atomic reviewed copy; return its previous value."""
    if column in READ_ONLY_COLUMNS:
        raise ValueError(f"La columna {column} está protegida y no se puede editar.")
    if row_index < 0:
        raise ValueError("La fila seleccionada no es válida.")

    temporary = reviewed_path.with_name(f".{reviewed_path.name}.{uuid4().hex}.tmp")
    previous_value: str | None = None
    found_row = False
    try:
        with source_path.open("r", encoding="latin-1", newline="") as source:
            reader = csv.reader(source, delimiter=";")
            headers = next(reader, None)
            if not headers or column not in headers:
                raise ValueError(f"El consolidado no contiene la columna {column}.")
            column_index = headers.index(column)
            with temporary.open("w", encoding="latin-1", newline="") as output:
                writer = csv.writer(output, delimiter=";", lineterminator="\n")
                writer.writerow(headers)
                for current_index, row in enumerate(reader):
                    if len(row) != len(headers):
                        raise ValueError(f"La fila {current_index + 2} tiene un número de columnas inválido.")
                    if current_index == row_index:
                        previous_value = row[column_index]
                        row[column_index] = new_value
                        found_row = True
                    writer.writerow(row)
        if not found_row:
            raise IndexError("La póliza seleccionada ya no está en el consolidado.")
        os.replace(temporary, reviewed_path)
        return previous_value or ""
    finally:
        if temporary.exists():
            temporary.unlink()


def append_change_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as audit:
        audit.write(json.dumps(record, ensure_ascii=False) + "\n")
        audit.flush()
        os.fsync(audit.fileno())
