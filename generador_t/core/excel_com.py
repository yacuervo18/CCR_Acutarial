"""Manejo de Excel por COM: instancia propia, cierre seguro y errores legibles.

- Siempre se abre un Excel NUEVO y oculto (DispatchEx). Antes se usaba
  EnsureDispatch, que puede engancharse al Excel que el usuario ya tiene
  abierto: si ese Excel estaba ocupado (editando una celda, con un cuadro de
  dialogo, etc.) la macro fallaba con 0x800AC472.
- Al cerrar, si Excel quedo bloqueado (p. ej. la macro tuvo un error de VBA y
  quedo en modo depuracion), se reintenta y, si no responde, se cierra a la
  fuerza ESA instancia (nunca el Excel del usuario). Asi el error original no
  queda tapado por un error al cerrar.
"""
from __future__ import annotations

import subprocess
import time
from typing import Callable, Optional, Tuple

Logger = Callable[[str], None]

# HRESULTs comunes de Excel por COM -> explicacion en espanol.
_ERRORES_CONOCIDOS = {
    -2146777998: "Excel quedo ocupado/bloqueado (0x800AC472). Suele pasar cuando la macro "
                 "tuvo un error de VBA o mostro un cuadro de dialogo que no se ve porque Excel corre oculto.",
    -2146827284: "Excel rechazo la operacion (0x800A03EC).",
    -2147417848: "Excel se cerro o se desconecto inesperadamente (RPC_E_DISCONNECTED).",
    -2147418111: "Excel estaba ocupado y rechazo la llamada (RPC_E_CALL_REJECTED).",
    -2147023174: "No se pudo comunicar con Excel (el servidor RPC no esta disponible).",
}


def abrir_excel() -> Tuple[object, Optional[int]]:
    """Abre una instancia nueva y oculta de Excel. Devuelve (excel, pid)."""
    import win32com.client as win32

    excel = win32.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    pid = None
    try:
        import win32process

        _, pid = win32process.GetWindowThreadProcessId(excel.Hwnd)
    except Exception:
        pass
    return excel, pid


def cerrar_excel(excel, wb=None, pid: Optional[int] = None, log: Logger = print) -> None:
    """Cierra el libro sin guardar y la instancia de Excel, sin lanzar errores."""
    cerro_bien = True
    if wb is not None:
        cerro_bien = False
        for _ in range(3):
            try:
                wb.Close(SaveChanges=False)
                cerro_bien = True
                break
            except Exception:
                time.sleep(3)
    try:
        excel.Quit()
    except Exception:
        cerro_bien = False
    if not cerro_bien and pid:
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        log("Excel no respondia y se cerro a la fuerza (era la instancia propia del proceso, "
            "no el Excel del usuario).")


def explicar_error(e: BaseException) -> str:
    """Mensaje legible para errores de COM (incluye el detalle que da Excel/VBA)."""
    try:
        import pywintypes
    except ImportError:
        return str(e)
    if not isinstance(e, pywintypes.com_error):
        return str(e)
    hresult = e.args[0] if e.args else None
    excepinfo = e.args[2] if len(e.args) > 2 else None
    detalle = ""
    if excepinfo and len(excepinfo) > 2 and excepinfo[2]:
        detalle = str(excepinfo[2]).strip()
        # el codigo "de adentro" (p. ej. el de VBA) suele venir en excepinfo[5]
        if len(excepinfo) > 5 and excepinfo[5] in _ERRORES_CONOCIDOS:
            hresult = excepinfo[5]
    base = _ERRORES_CONOCIDOS.get(hresult, f"Error de Excel ({hresult}): {e.args[1] if len(e.args) > 1 else e}")
    return f"{base} Detalle de Excel: {detalle}" if detalle else base
