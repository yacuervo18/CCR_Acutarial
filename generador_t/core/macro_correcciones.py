"""Refleja en una copia de la macro calculada las correcciones de póliza.

La macro original (5_Macro_consolidada) nunca se modifica: se copia y las
correcciones registradas en la bitácora se escriben como valores en la hoja
'BBDD IFRS 17'. No se recalcula nada.
"""
from __future__ import annotations

import datetime
import json
import math
import shutil
import uuid
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from . import paths
from .consolidacion import _clave_poliza, _fecha_com, _ultima_fila_col
from .excel_com import abrir_excel, cerrar_excel, explicar_error

Logger = Callable[[str], None]

HOJA = "BBDD IFRS 17"
FILA_ENCABEZADOS = 3
PRIMERA_FILA_DATOS = 4
# fila_csv cuenta el encabezado como fila 1 y la macro tiene 3 filas antes de los datos.
DESFASE_FILA_MACRO = PRIMERA_FILA_DATOS - 2


def leer_correcciones(ruta: Path, run_id: str) -> List[dict]:
    """Última corrección de cada celda (fila, columna), conservando el valor original."""
    if not ruta.is_file():
        return []
    por_celda: Dict[Tuple[int, str], dict] = {}
    with ruta.open("r", encoding="utf-8") as bitacora:
        for linea in bitacora:
            if not linea.strip():
                continue
            registro = json.loads(linea)
            if registro.get("run_id") != run_id:
                continue
            clave = (int(registro["fila_csv"]), str(registro["columna"]))
            if clave in por_celda:
                por_celda[clave]["valor_nuevo"] = registro["valor_nuevo"]
            else:
                por_celda[clave] = dict(registro)
    return list(por_celda.values())


def _como_numero(texto) -> Optional[float]:
    if isinstance(texto, bool):
        return None
    if isinstance(texto, (int, float)):
        return float(texto)
    try:
        return float(str(texto).strip())
    except ValueError:
        pass
    try:
        return _fecha_com(datetime.datetime.strptime(str(texto).strip(), "%Y/%m/%d"))
    except ValueError:
        return None


def valor_para_celda(nuevo: str, actual):
    """Texto del CSV -> valor de la celda. Si la celda es numérica el valor
    debe poder leerse como número o fecha (AAAA/MM/DD); si no, se detiene."""
    if nuevo is None or str(nuevo).strip() == "":
        return None
    numero = _como_numero(nuevo)
    if isinstance(actual, (int, float)) and not isinstance(actual, bool):
        if numero is None:
            raise ValueError(f"'{nuevo}' no es un número ni una fecha y la celda es numérica.")
        return numero
    if actual is None and numero is not None:
        return numero
    return str(nuevo)


def _iguales(a, b) -> bool:
    na, nb = _como_numero(a), _como_numero(b)
    if na is not None and nb is not None:
        return math.isclose(na, nb, rel_tol=1e-6, abs_tol=1e-4)
    return str(a if a is not None else "").strip() == str(b if b is not None else "").strip()


def aplicar_correcciones_a_macro(
    params, run_id: str, log: Logger = print
) -> Optional[Path]:
    """Crea la copia de la macro con las correcciones; devuelve su ruta (o None
    si la corrida no tiene correcciones)."""
    import pythoncom

    clave = params.clave_periodo
    correcciones = leer_correcciones(paths.correcciones_path(clave, run_id), run_id)
    if not correcciones:
        return None
    origen = paths.macro_copia_path(clave)
    if not origen.is_file():
        raise FileNotFoundError(f"No existe la macro calculada: {origen}")
    destino = paths.macro_con_correcciones_path(clave, run_id)
    temporal = destino.with_name(f"~tmp_{uuid.uuid4().hex}.xlsm")
    shutil.copy2(origen, temporal)

    pythoncom.CoInitialize()
    excel = wb = pid = None
    try:
        try:
            excel, pid = abrir_excel()
            excel.AutomationSecurity = 3  # sin ejecutar macros al abrir la copia
            wb = excel.Workbooks.Open(str(temporal), 0, False)
            sh = wb.Sheets(HOJA)
            nrows, ncols = _ultima_fila_col(sh)
            encabezados = sh.Range(sh.Cells(FILA_ENCABEZADOS, 1), sh.Cells(FILA_ENCABEZADOS, ncols)).Value2[0]
            columnas = {str(h).strip(): i + 1 for i, h in enumerate(encabezados) if h is not None}
            if "NMPOLIZA" not in columnas:
                raise KeyError(f"La hoja {HOJA} no tiene la columna NMPOLIZA.")
            col_pol = columnas["NMPOLIZA"]
            polizas = sh.Range(sh.Cells(PRIMERA_FILA_DATOS, col_pol), sh.Cells(nrows, col_pol)).Value2
            claves = [_clave_poliza(f[0]) for f in polizas] if nrows >= PRIMERA_FILA_DATOS else []

            plan = []
            for c in correcciones:
                columna = c["columna"]
                if columna not in columnas:
                    raise KeyError(f"La hoja {HOJA} no tiene la columna {columna}.")
                poliza = _clave_poliza(c["NMPOLIZA"])
                fila = int(c["fila_csv"]) + DESFASE_FILA_MACRO
                indice = fila - PRIMERA_FILA_DATOS
                if not (0 <= indice < len(claves) and claves[indice] == poliza):
                    candidatas = [PRIMERA_FILA_DATOS + i for i, k in enumerate(claves) if k == poliza]
                    if len(candidatas) != 1:
                        raise ValueError(
                            f"No se pudo ubicar de forma única la póliza {poliza} en la macro."
                        )
                    fila = candidatas[0]
                celda = sh.Cells(fila, columnas[columna])
                if celda.HasFormula:
                    raise ValueError(
                        f"La celda {columna} de la póliza {poliza} contiene una fórmula; no se sobrescribe."
                    )
                actual = celda.Value2
                if not _iguales(actual, c.get("valor_anterior")):
                    log(f"  Aviso: {columna} de {poliza} en la macro es {actual!r} y la bitácora "
                        f"registra {c.get('valor_anterior')!r} como valor anterior.")
                plan.append((fila, columnas[columna], columna, poliza, valor_para_celda(c["valor_nuevo"], actual)))

            for fila, col, _, _, valor in plan:
                sh.Cells(fila, col).Value2 = valor
            for fila, col, columna, poliza, valor in plan:
                leido = sh.Cells(fila, col).Value2
                if not _iguales(leido, valor):
                    raise ValueError(f"{columna} de {poliza} no quedó con el valor esperado ({leido!r}).")
            wb.Save()
        except Exception as error:
            raise RuntimeError(explicar_error(error)) from error
        finally:
            if excel is not None:
                cerrar_excel(excel, wb, pid, log)
        temporal.replace(destino)
    finally:
        pythoncom.CoUninitialize()
        if temporal.exists():
            temporal.unlink()
    log(f"Macro con {len(correcciones)} corrección(es) de póliza guardada en {destino}")
    return destino
