"""Automatiza la Macro_consolidacion.xlsm: pega las Ts, corre el calculo y
devuelve la hoja 'BBDD IFRS 17' resultante.

Esto reemplaza el paso manual que se hacia antes (abrir la macro, pegar cada
T a mano, poner los parametros y darle click a Calcular).
"""
from __future__ import annotations

import datetime
import time
from pathlib import Path
from typing import Callable, List, Tuple

import numpy as np
import pandas as pd

from . import paths
from .excel_com import abrir_excel, cerrar_excel, explicar_error
from .params import Params

Logger = Callable[[str], None]
# progreso(actual, total, texto): avance del paso para la barra de la app.
Progreso = Callable[[int, int, str], None]


def _sin_progreso(actual: int, total: int, texto: str) -> None:
    pass

NOMBRE_MACRO_CALCULAR = "Conversion_T_To_BBDD_IFRS17"


EXCEL_EPOCH = datetime.datetime(1899, 12, 30)


def _valor_com(v):
    """Convierte un valor de pandas a algo que pywin32 pueda escribir por COM.

    Nota: en esta combinacion de pywin32 + Python 3.14, escribir objetos
    datetime.datetime directamente a una celda falla con OSError 22 (invalid
    argument) — un problema de marshaling de VARIANT DATE. La solucion es
    enviar el serial de Excel (numero) en vez del objeto datetime; la celda
    ya tiene formato de fecha en la plantilla, asi que se muestra igual.
    """
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, pd.Timestamp):
        v = v.to_pydatetime()
    if isinstance(v, datetime.datetime):
        return (v - EXCEL_EPOCH).total_seconds() / 86400.0
    if isinstance(v, np.generic):
        return v.item()
    return v


TAMANO_LOTE = 3000  # COM falla al escribir arreglos 2D demasiado grandes de una vez


def _escribir_dataframe(sh, df: pd.DataFrame) -> None:
    used = sh.UsedRange
    nrows_actual = used.Rows.Count
    ncols_sheet = used.Columns.Count
    if nrows_actual > 1:
        sh.Range(sh.Cells(2, 1), sh.Cells(nrows_actual, ncols_sheet)).ClearContents()
    if df.empty:
        return
    ncols = len(df.columns)
    filas = [[_valor_com(v) for v in fila] for fila in df.itertuples(index=False, name=None)]
    for inicio in range(0, len(filas), TAMANO_LOTE):
        lote = filas[inicio:inicio + TAMANO_LOTE]
        fila_inicio = 2 + inicio
        destino = sh.Range(sh.Cells(fila_inicio, 1), sh.Cells(fila_inicio + len(lote) - 1, ncols))
        destino.Value = lote


def _fecha_com(d: datetime.date) -> float:
    """Serial de Excel para una fecha (ver nota en _valor_com sobre el bug
    de pywin32 + Python 3.14 al escribir objetos datetime por COM)."""
    return (datetime.datetime(d.year, d.month, d.day) - EXCEL_EPOCH).total_seconds() / 86400.0


def _set_parametros(wb, params: Params) -> None:
    sh = wb.Sheets("Parametros")
    sh.Range("C4").Value = _fecha_com(params.fecha_calculo)
    sh.Range("C5").Value = params.smmlv
    sh.Range("C6").Value = params.inflacion
    sh.Range("C7").Value = params.interes_real
    sh.Range("C8").Value = int(params.ramo)
    sh.Range("C9").Value = _fecha_com(params.fecha_valoracion)


def _origen_ts(params: Params) -> Path:
    """Carpeta de donde se pegan las Ts. ARL usa las Ts finales (con hoja
    'Integridad y Exactitud'); LEY100 no lleva evidencias SOX, asi que usa
    directo las descargadas convertidas a xlsx."""
    if params.es_ley100:
        return paths.ts_mod_dir(params.clave_periodo)
    return paths.archivos_t_final_dir(params.clave_periodo)


def _leer_t(carpeta: Path, numero_t: int) -> pd.DataFrame:
    origen = carpeta / f"T{numero_t}.xlsx"
    if not origen.exists():
        raise FileNotFoundError(
            f"No existe {origen}. Revisa que las Ts esten descargadas y convertidas a xlsx."
        )
    return pd.read_excel(origen, sheet_name=0)


GASTO_EN_CERO = "RIESGOS ADICIONALES"


def ajustar_t4_gastos(df: pd.DataFrame, log: Logger = print) -> pd.DataFrame:
    """Paso previo a consolidar (ambos ramos): en la T4, las filas cuyo GASTO
    es 'GASTO RIESGOS ADICIONALES' quedan en 0 (PORCENTAJE y, si trae, VALOR).

    Se aplica solo a lo que se pega en la macro: el archivo descargado de
    Osiris (evidencia) no se modifica; la T4 ajustada queda en la copia de la
    macro guardada."""
    if "GASTO" not in df.columns:
        raise KeyError("La T4 no tiene la columna 'GASTO'; no se pudo aplicar el ajuste de riesgos adicionales.")
    df = df.copy()
    filtro = df["GASTO"].astype(str).str.upper().str.contains(GASTO_EN_CERO, na=False)
    for col in ("PORCENTAJE", "VALOR"):
        if col in df.columns:
            con_valor = filtro & df[col].notna() if col == "VALOR" else filtro
            df.loc[con_valor, col] = 0
    log(f"T4: {int(filtro.sum())} filas de 'GASTO RIESGOS ADICIONALES' puestas en 0.")
    return df


def _clave_poliza(v) -> str:
    """87020008496, 87020008496.0 y '87020008496' -> '87020008496'."""
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    s = str(v).strip()
    return s[:-2] if s.endswith(".0") else s


def cargar_tasas_ley100(ruta: Path) -> dict:
    """Lee el Excel de tasas de Ley 100: {poliza: tasa}. Primera columna = poliza
    (se acepta 'Poliza'/'Póliza'), y la columna POINTERES_TECNICO = tasa."""
    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encontro el archivo de tasas de Ley 100 ({ruta}). Cargalo desde la barra lateral de la app."
        )
    df = pd.read_excel(ruta, dtype=object)
    if "POINTERES_TECNICO" not in df.columns:
        raise KeyError(f"El archivo {ruta.name} no tiene la columna POINTERES_TECNICO.")
    col_poliza = next((c for c in df.columns if "LIZA" in str(c).upper()), df.columns[0])
    tasas = {}
    for pol, tasa in zip(df[col_poliza], df["POINTERES_TECNICO"]):
        if pd.isna(pol) or pd.isna(tasa):
            continue
        tasas[_clave_poliza(pol)] = float(tasa)
    return tasas


def _columna(sh, col: int, fila_ini: int, fila_fin: int) -> list:
    valores = sh.Range(sh.Cells(fila_ini, col), sh.Cells(fila_fin, col)).Value
    if fila_ini == fila_fin:  # COM devuelve un escalar si es una sola celda
        return [valores]
    return [fila[0] for fila in valores]


def _ultima_fila_col(sh) -> tuple:
    """Ultima fila/columna con datos (UsedRange puede no empezar en A1)."""
    used = sh.UsedRange
    return used.Row + used.Rows.Count - 1, used.Column + used.Columns.Count - 1


def corregir_tasas_ley100(wb, tasas: dict, log: Logger = print) -> int:
    """En la hoja 'BBDD IFRS 17' (ya calculada): para las polizas del archivo
    de tasas, POINTERES_TECNICO = tasa del archivo y luego TASA p1 = POINTERES_TECNICO.
    Se escribe solo en las celdas de esas polizas. Devuelve cuantas filas cambio."""
    sh = wb.Sheets("BBDD IFRS 17")
    nrows, ncols = _ultima_fila_col(sh)
    encabezados = sh.Range(sh.Cells(3, 1), sh.Cells(3, ncols)).Value[0]
    idx = {str(h).strip(): i + 1 for i, h in enumerate(encabezados) if h is not None}
    faltan = [c for c in ("NMPOLIZA", "POINTERES_TECNICO", "TASA p1") if c not in idx]
    if faltan:
        raise KeyError(f"La hoja BBDD IFRS 17 no tiene las columnas {faltan}.")
    if nrows < 4:
        log("BBDD IFRS 17 sin filas: no hay tasas que corregir.")
        return 0

    polizas = _columna(sh, idx["NMPOLIZA"], 4, nrows)
    cambiadas, encontradas = 0, set()
    for i, pol in enumerate(polizas):
        clave = _clave_poliza(pol)
        if clave in tasas:
            fila = 4 + i
            sh.Cells(fila, idx["POINTERES_TECNICO"]).Value = tasas[clave]
            # TASA p1 se copia de POINTERES_TECNICO ya corregido
            sh.Cells(fila, idx["TASA p1"]).Value = sh.Cells(fila, idx["POINTERES_TECNICO"]).Value
            cambiadas += 1
            encontradas.add(clave)
    no_estan = sorted(set(tasas) - encontradas)
    log(f"Tasas Ley 100: {cambiadas} filas corregidas en BBDD IFRS 17 "
        f"({len(encontradas)} de {len(tasas)} polizas del archivo).")
    if no_estan:
        log(f"  {len(no_estan)} polizas del archivo de tasas no estan en BBDD IFRS 17 "
            f"(p. ej. {', '.join(no_estan[:5])}).")
    return cambiadas


def _pegar_t(wb, carpeta: Path, numero_t: int, log: Logger) -> None:
    df = _leer_t(carpeta, numero_t)
    if numero_t == 4:
        df = ajustar_t4_gastos(df, log)
    _escribir_dataframe(wb.Sheets(f"T{numero_t}"), df)
    log(f"T{numero_t} pegada en la macro ({len(df)} filas).")


def _pegar_adicional(wb, carpeta: Path, log: Logger) -> None:
    df = _leer_t(carpeta, 11)
    if "DSLOGIN_MODIFICA" in df.columns:
        df = df.drop(columns=["DSLOGIN_MODIFICA"])
    _escribir_dataframe(wb.Sheets("Adicional"), df)
    log(f"T11 (nueva produccion) pegada en 'Adicional' ({len(df)} filas).")




def leer_bbdd_ifrs17_raw(wb) -> Tuple[List[str], List[tuple]]:
    """Lee la hoja 'BBDD IFRS 17' con lectura masiva (rapida) via COM.

    Los encabezados reales estan en la fila 3 (filas 1-2 son metadatos/grupos).
    """
    sh = wb.Sheets("BBDD IFRS 17")
    nrows, ncols = _ultima_fila_col(sh)
    rango = sh.Range(sh.Cells(3, 1), sh.Cells(nrows, ncols))
    data = rango.Value
    headers = list(data[0])
    rows = list(data[1:])
    return headers, rows


def consolidar(
    params: Params,
    macro_password: str,
    guardar_copia: bool = True,
    log: Logger = print,
    progreso: Progreso = _sin_progreso,
) -> Tuple[List[str], List[tuple], Path]:
    """Pega T1..T11 en la macro, corre el calculo y lee 'BBDD IFRS 17'.

    Devuelve (headers, rows, ruta_copia_guardada). La plantilla original
    (Macro_consolidacion.xlsm) nunca se sobreescribe: el resultado calculado
    se guarda en una copia fechada dentro de archivos_T/{fecha}/.
    """
    import pythoncom

    fecha = params.clave_periodo
    carpeta_ts = _origen_ts(params)

    # Streamlit corre el script en un hilo que no es el principal; COM exige
    # que cada hilo que lo use llame CoInitialize (si no, sale el error
    # "-2147221008, no se ha llamado a CoInitialize").
    # abrir + parametros + 11 Ts + calculo + lectura (+ copia)
    # (+1 si es Ley 100: correccion de tasas despues de la macro)
    total = 15 + (1 if guardar_copia else 0) + (1 if params.es_ley100 else 0)
    tasas = cargar_tasas_ley100(paths.tasas_ley100_path()) if params.es_ley100 else None
    pythoncom.CoInitialize()
    excel = wb = pid = None
    paso = "abrir Excel"
    try:
        progreso(0, total, "Abriendo la macro en Excel")
        log("Abriendo Macro_consolidacion.xlsm (en un Excel propio y oculto)...")
        try:
            excel, pid = abrir_excel()
            paso = "abrir la macro (revisa la contrasena)"
            wb = excel.Workbooks.Open(str(paths.macro_path()), Password=macro_password)

            paso = "escribir parametros"
            progreso(1, total, "Escribiendo parametros")
            log("Escribiendo hoja Parametros...")
            _set_parametros(wb, params)

            for t in range(1, 11):
                paso = f"pegar T{t}"
                progreso(1 + t, total, f"Pegando T{t} de 11")
                _pegar_t(wb, carpeta_ts, t, log)
            paso = "pegar T11"
            progreso(12, total, "Pegando T11 de 11 (nueva produccion)")
            _pegar_adicional(wb, carpeta_ts, log)

            paso = f"calcular la macro ({NOMBRE_MACRO_CALCULAR})"
            progreso(13, total, "Calculando la macro (puede tardar varios minutos)")
            log("Ejecutando macro de calculo (Conversion_T_To_BBDD_IFRS17)... esto puede tardar varios minutos.")
            inicio = time.time()
            excel.Application.Run(f"'{wb.Name}'!{NOMBRE_MACRO_CALCULAR}")
            log(f"Macro de calculo finalizada ({time.time() - inicio:.0f}s).")

            if tasas is not None:
                paso = "corregir tasas de Ley 100"
                progreso(14, total, "Corrigiendo tasas de Ley 100 (POINTERES_TECNICO y TASA p1)")
                corregir_tasas_ley100(wb, tasas, log)

            paso = "leer hoja BBDD IFRS 17"
            progreso(total - 2 if guardar_copia else total - 1, total, "Leyendo hoja BBDD IFRS 17")
            headers, rows = leer_bbdd_ifrs17_raw(wb)
            log(f"BBDD IFRS 17 leida: {len(rows)} filas, {len(headers)} columnas.")

            ruta_copia = None
            if guardar_copia:
                paso = "guardar copia de la macro calculada"
                progreso(total - 1, total, "Guardando copia de la macro calculada")
                ruta_copia = paths.macro_copia_path(fecha)
                paths.asegurar_directorio(ruta_copia.parent)
                wb.SaveAs(str(ruta_copia), AddToMru=False)
                log(f"Copia calculada guardada en {ruta_copia}")

            progreso(total, total, "Consolidacion lista")

            return headers, rows, ruta_copia
        except Exception as e:
            # Se reporta el error ORIGINAL con el paso donde ocurrio (antes, un
            # segundo error al cerrar Excel lo tapaba).
            log(f"Fallo en el paso '{paso}': {explicar_error(e)}")
            raise RuntimeError(f"Fallo en el paso '{paso}': {explicar_error(e)}") from e
        finally:
            if excel is not None:
                cerrar_excel(excel, wb, pid, log)
    finally:
        pythoncom.CoUninitialize()
