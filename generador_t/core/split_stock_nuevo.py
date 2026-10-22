"""Convierte la hoja 'BBDD IFRS 17' (ya calculada) en las 2 Ts consolidadas
finales: Stock (polizas con FEVIGENCIA_INICIAL anterior al corte) y Nuevo
(desde el corte en adelante). El corte es params.fecha_minima_prod_nueva.

En ambos ramos el usuario elige la fecha de corte y si Stock y/o Nuevo salen
vacias (solo encabezados). LEY100 ademas va sin las reglas fijas de ARL, con 'Asegurado' renumerado desde 1 y en latin-1 (validado
contra el ejemplo real 202608_t_consolidada_Nuevo_Ley100.csv).

La logica de formato de valores fue validada celda a celda contra los
archivos de ejemplo 202608_t_consolidada_{Stock,Nuevo}_RM.csv (099.8%+ de
coincidencia exacta; el pequeno remanente son valores monetarios recalculados
por formulas de la macro que pueden variar en el ultimo decimal segun los
parametros de calculo usados).
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Callable, List, Tuple

import pandas as pd

from . import paths
from .params import Params

Logger = Callable[[str], None]
# progreso(actual, total, texto): avance del paso para la barra de la app.
Progreso = Callable[[int, int, str], None]


def _sin_progreso(actual: int, total: int, texto: str) -> None:
    pass

EXCEL_EPOCH = datetime.datetime(1899, 12, 30)
MESES = [
    "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO",
    "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE",
]


def _es_columna_fecha(nombre: str) -> bool:
    up = str(nombre).upper()
    if any(up.startswith(m) for m in MESES):
        return False
    return up.startswith("FE") or "FECHA" in up


def _a_fecha_str(v):
    if v is None or v == "":
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, bool):
        return v
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y/%m/%d")
    if isinstance(v, (int, float)):
        return (EXCEL_EPOCH + datetime.timedelta(days=float(v))).strftime("%Y/%m/%d")
    return v


def _formatea_general(v):
    if v is None:
        return ""
    if isinstance(v, datetime.datetime):
        if v.tzinfo is not None:
            v = datetime.datetime(v.year, v.month, v.day, v.hour, v.minute, v.second)
        if v.year <= 1900:
            # celda numerica formateada como fecha por error (serial pequeno)
            return str((v - EXCEL_EPOCH).days)
        return v.strftime("%Y/%m/%d")
    if isinstance(v, bool):
        return v
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        return repr(v)
    return v


def formatear_bbdd_ifrs17(
    headers: List[str], rows: List[tuple], aplicar_reglas: bool = True
) -> pd.DataFrame:
    """Aplica el formato final (fechas dd/mm/aaaa, numeros sin '.0' de sobra,
    banderas de texto tipo 'V' preservadas) a los datos crudos leidos de la
    hoja 'BBDD IFRS 17' via COM."""
    es_fecha = [_es_columna_fecha(h) for h in headers]

    formatted_rows = []
    for row in rows:
        nueva_fila = [
            _a_fecha_str(v) if es_col_fecha else _formatea_general(v)
            for v, es_col_fecha in zip(row, es_fecha)
        ]
        formatted_rows.append(nueva_fila)

    df = pd.DataFrame(formatted_rows, columns=headers)
    if aplicar_reglas:
        _aplicar_reglas_negocio(df)
    return df


def _aplicar_reglas_negocio(df: pd.DataFrame) -> None:
    """Ajustes que el proceso manual siempre aplicaba despues de calcular la
    macro (rescatados del pipeline anterior antes de depurarlo):
      - POINTERES_TECNICO se iguala a TASA p1.
      - % GA_1 se deja fijo en 2 (supuesto de gastos de adquisicion del ramo).
    Se aplican en sitio sobre df.
    """
    if "TASA p1" in df.columns and "POINTERES_TECNICO" in df.columns:
        df["POINTERES_TECNICO"] = df["TASA p1"]
    if "% GA_1" in df.columns:
        df["% GA_1"] = "2"


def dividir_stock_nuevo(df: pd.DataFrame, params: Params) -> Tuple[pd.DataFrame, pd.DataFrame]:
    fevigencia = pd.to_datetime(df["FEVIGENCIA_INICIAL"], format="%Y/%m/%d")
    corte = pd.Timestamp(params.cutoff_stock_nuevo)
    # Stock: inicio de vigencia antes del corte; Nuevo: desde el corte.
    # Cualquiera puede quedar vacia (solo columnas) si el usuario lo elige.
    stock = df.iloc[0:0].copy() if params.stock_vacia else df[fevigencia < corte].copy()
    nuevo = df.iloc[0:0].copy() if params.nuevo_vacia else df[fevigencia >= corte].copy()
    # Con Stock vacia, la Nuevo de Ley 100 se numera desde 1 (asi venia el
    # archivo real de agosto). Si Stock trae polizas se deja la numeracion de
    # la macro, para no repetir numeros entre Stock y Nuevo.
    if params.es_ley100 and params.stock_vacia and "Asegurado" in nuevo.columns:
        nuevo["Asegurado"] = [str(i) for i in range(1, len(nuevo) + 1)]
    return stock, nuevo


def generar_ts_consolidadas(
    headers: List[str],
    rows: List[tuple],
    params: Params,
    log: Logger = print,
    progreso: Progreso = _sin_progreso,
) -> Tuple[Path, Path]:
    """Formatea, divide y guarda las 2 Ts consolidadas finales (Stock/Nuevo).

    Devuelve las rutas de los 2 csv generados.
    """
    progreso(0, 3, "Dando formato a BBDD IFRS 17")
    log(f"Dando formato a {len(rows)} filas de BBDD IFRS 17...")
    # Las reglas fijas (POINTERES_TECNICO = TASA p1, % GA_1 = 2) son solo de ARL.
    df = formatear_bbdd_ifrs17(headers, rows, aplicar_reglas=not params.es_ley100)
    progreso(1, 3, "Separando Stock y Nuevo")
    stock, nuevo = dividir_stock_nuevo(df, params)

    progreso(2, 3, "Guardando csv")
    ruta_stock = paths.consolidada_csv_path(params.clave_periodo, "Stock")
    ruta_nuevo = paths.consolidada_csv_path(params.clave_periodo, "Nuevo")
    paths.asegurar_directorio(ruta_stock.parent)

    stock.to_csv(ruta_stock, sep=";", index=False, encoding=params.encoding_consolidada)
    nuevo.to_csv(ruta_nuevo, sep=";", index=False, encoding=params.encoding_consolidada)

    log(f"T consolidada Stock: {len(stock)} filas -> {ruta_stock}")
    log(f"T consolidada Nuevo: {len(nuevo)} filas -> {ruta_nuevo}")
    progreso(3, 3, "Ts consolidadas listas")
    return ruta_stock, ruta_nuevo
