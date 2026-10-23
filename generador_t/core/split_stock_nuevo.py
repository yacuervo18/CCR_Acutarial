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
import json
from dataclasses import replace
from pathlib import Path
from typing import Callable, List, Tuple
from uuid import uuid4

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


def _fin_mes_anterior(fecha: datetime.date) -> datetime.date:
    return fecha.replace(day=1) - datetime.timedelta(days=1)


def _escribir_manifest(params: Params, estado: str, **conteos) -> Path:
    """Registro de la corrida: parametros usados y conteos. Se reescribe en cada
    etapa; conserva lo que ya tenia (p. ej. la hora de generacion del total)."""
    ruta = paths.manifest_path(params.clave_periodo)
    paths.asegurar_directorio(ruta.parent)
    actual = {}
    if ruta.exists():
        try:
            actual = json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"No se pudo leer el manifest de la corrida: {error}") from error
        if not isinstance(actual, dict):
            raise ValueError("El manifest de la corrida debe contener un objeto JSON.")
    ahora = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    actual.update(
        {
            "version": 1,
            "tipo_ramo": params.tipo_ramo,
            "periodo": params.fecha_valoracion_input,
            "fecha_valoracion_t": params.fecha_valoracion.isoformat(),
            "fecha_valoracion_t_1": _fin_mes_anterior(params.fecha_valoracion).isoformat(),
            "inflacion": params.inflacion,
            "smmlv": params.smmlv,
            "interes_real": params.interes_real,
            "fecha_corte_vigencia": params.cutoff_stock_nuevo.isoformat(),
            "stock_vacia": params.stock_vacia,
            "nuevo_vacia": params.nuevo_vacia,
            "codificacion": params.encoding_consolidada,
            "estado": estado,
            "actualizado_en": ahora,
        }
    )
    if estado == "consolidado_total":
        actual.update(
            {
                "run_id": uuid4().hex,
                "archivo_revisado": None,
                "cantidad_correcciones": 0,
                "revision_actualizada_en": None,
            }
        )
    if "total_generado_en" not in actual or estado == "consolidado_total":
        actual["total_generado_en"] = ahora
    actual.update(conteos)
    ruta.write_text(json.dumps(actual, indent=2, ensure_ascii=False), encoding="utf-8")
    return ruta


def generar_consolidado_total(
    headers: List[str],
    rows: List[tuple],
    params: Params,
    log: Logger = print,
    progreso: Progreso = _sin_progreso,
) -> Tuple[Path, pd.DataFrame]:
    """Etapa A: da formato a 'BBDD IFRS 17' y guarda el consolidado total
    (sin partir) con su manifest. Devuelve la ruta y el DataFrame en memoria."""
    progreso(0, 2, "Dando formato a BBDD IFRS 17")
    log(f"Dando formato a {len(rows)} filas de BBDD IFRS 17...")
    # Las reglas fijas (POINTERES_TECNICO = TASA p1, % GA_1 = 2) son solo de ARL.
    df = formatear_bbdd_ifrs17(headers, rows, aplicar_reglas=not params.es_ley100)

    progreso(1, 2, "Guardando consolidado total")
    ruta_total = paths.consolidada_total_path(params.clave_periodo)
    paths.asegurar_directorio(ruta_total.parent)
    df.to_csv(ruta_total, sep=";", index=False, encoding=params.encoding_consolidada)
    # Una nueva generacion invalida lo partido antes con otro consolidado.
    for tipo in ("Stock", "Nuevo"):
        paths.consolidada_csv_path(params.clave_periodo, tipo).unlink(missing_ok=True)
    paths.consolidada_stock_completo_path(params.clave_periodo).unlink(missing_ok=True)
    tamano_mb = ruta_total.stat().st_size / (1024 * 1024)
    _escribir_manifest(
        params,
        "consolidado_total",
        filas_total=len(df),
        columnas_total=len(df.columns),
        tamano_total_mb=round(tamano_mb, 2),
        archivo_total=ruta_total.name,
        filas_stock=None,
        filas_nuevo=None,
    )
    log(f"Consolidado total: {len(df)} filas, {len(df.columns)} columnas, {tamano_mb:.1f} MB -> {ruta_total}")
    progreso(2, 2, "Consolidado total listo")
    return ruta_total, df


def _partir_y_guardar(
    df: pd.DataFrame,
    params: Params,
    log: Logger,
    progreso: Progreso,
) -> Tuple[Path, Path]:
    progreso(0, 2, "Separando Stock y Nuevo")
    stock, nuevo = dividir_stock_nuevo(df, params)

    progreso(1, 2, "Guardando csv")
    ruta_stock = paths.consolidada_csv_path(params.clave_periodo, "Stock")
    ruta_nuevo = paths.consolidada_csv_path(params.clave_periodo, "Nuevo")
    ruta_stock_completo = paths.consolidada_stock_completo_path(params.clave_periodo)
    paths.asegurar_directorio(ruta_stock.parent)

    stock.to_csv(ruta_stock, sep=";", index=False, encoding=params.encoding_consolidada)
    nuevo.to_csv(ruta_nuevo, sep=";", index=False, encoding=params.encoding_consolidada)
    stock_completo = None
    if params.stock_vacia:
        params_stock_completo = replace(params, stock_vacia=False, nuevo_vacia=True)
        stock_completo, _ = dividir_stock_nuevo(df, params_stock_completo)
        stock_completo.to_csv(
            ruta_stock_completo,
            sep=";",
            index=False,
            encoding=params.encoding_consolidada,
        )
    else:
        ruta_stock_completo.unlink(missing_ok=True)
    _escribir_manifest(
        params,
        "completo",
        filas_stock=len(stock),
        filas_nuevo=len(nuevo),
        archivo_stock=ruta_stock.name,
        archivo_nuevo=ruta_nuevo.name,
        filas_stock_completo=len(stock_completo) if stock_completo is not None else len(stock),
        archivo_stock_completo=(
            ruta_stock_completo.name if stock_completo is not None else ruta_stock.name
        ),
    )

    log(f"T consolidada Stock: {len(stock)} filas -> {ruta_stock}")
    if stock_completo is not None:
        log(
            f"Stock completo de evidencia: {len(stock_completo)} filas "
            f"-> {ruta_stock_completo}"
        )
    log(f"T consolidada Nuevo: {len(nuevo)} filas -> {ruta_nuevo}")
    progreso(2, 2, "Ts consolidadas listas")
    return ruta_stock, ruta_nuevo


def partir_desde_total(
    params: Params,
    log: Logger = print,
    progreso: Progreso = _sin_progreso,
) -> Tuple[Path, Path]:
    """Etapa B: lee el consolidado total guardado en disco y lo parte en
    Stock y Nuevo. No necesita Osiris ni Excel."""
    ruta_total = paths.consolidada_total_path(params.clave_periodo)
    if not ruta_total.exists():
        raise FileNotFoundError(f"No existe el consolidado total: {ruta_total}")
    ruta_manifest = paths.manifest_path(params.clave_periodo)
    if ruta_manifest.exists():
        try:
            manifest = json.loads(ruta_manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"No se pudo validar el registro de generación: {error}") from error
        if not isinstance(manifest, dict):
            raise ValueError("El registro de generación tiene un formato inválido.")
        archivo_revisado = manifest.get("archivo_revisado")
        if archivo_revisado:
            run_id = manifest.get("run_id")
            if not isinstance(run_id, str):
                raise ValueError("El registro no identifica la corrida de la revisión.")
            ruta_revisada = paths.consolidada_revisada_path(params.clave_periodo, run_id)
            if archivo_revisado != ruta_revisada.name:
                raise ValueError("El archivo revisado no corresponde a la corrida activa.")
            if not ruta_revisada.is_file():
                raise FileNotFoundError(f"No existe el consolidado revisado: {ruta_revisada}")
            ruta_total = ruta_revisada
    # Todo como texto y sin NaN, para conservar exactamente lo guardado.
    df = pd.read_csv(
        ruta_total, sep=";", dtype=str, keep_default_na=False, encoding=params.encoding_consolidada
    )
    log(f"Consolidado {'revisado' if ruta_total != paths.consolidada_total_path(params.clave_periodo) else 'total'} leido: {len(df)} filas.")
    return _partir_y_guardar(df, params, log, progreso)


def generar_ts_consolidadas(
    headers: List[str],
    rows: List[tuple],
    params: Params,
    log: Logger = print,
    progreso: Progreso = _sin_progreso,
) -> Tuple[Path, Path]:
    """Corrida completa: consolidado total + Stock y Nuevo (el DataFrame se
    reutiliza en memoria). Devuelve las rutas de Stock y Nuevo."""
    _, df = generar_consolidado_total(headers, rows, params, log, progreso)
    return _partir_y_guardar(df, params, log, progreso)
