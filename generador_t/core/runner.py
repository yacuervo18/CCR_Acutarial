"""Orquesta la generacion de Stock/Nuevo sin depender de una interfaz."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence, TypeVar

from . import consolidacion, evidencias, split_stock_nuevo
from .descarga_ts import descargar_ts
from .params import Params

Logger = Callable[[str], None]
Progress = Callable[[str, int, int, str], None]
Result = TypeVar("Result")


def _sin_log(mensaje: str) -> None:
    pass


def _sin_progreso(paso: str, actual: int, total: int, mensaje: str) -> None:
    pass


@dataclass(frozen=True)
class GeneratedFiles:
    stock: Path
    nuevo: Path


class GenerationError(RuntimeError):
    """Fallo de un paso con mensajes depurados de credenciales."""


def _redactar(mensaje: str, secretos: Sequence[str]) -> str:
    for secreto in secretos:
        if secreto:
            mensaje = mensaje.replace(secreto, "[REDACTADO]")
    return mensaje


def generar(
    params: Params,
    usuario_osiris: str,
    contrasena_osiris: str,
    contrasena_macro: str,
    log: Logger = _sin_log,
    progreso: Progress = _sin_progreso,
) -> GeneratedFiles:
    """Ejecuta el proceso completo y devuelve las rutas de Stock y Nuevo.

    Las credenciales solo se usan en memoria durante esta llamada. No se
    guardan en los parametros y se filtran de los mensajes de log y error.
    """
    if not usuario_osiris or not contrasena_osiris or not contrasena_macro:
        raise ValueError("Se requieren las credenciales de Osiris y de la macro.")

    secretos = (usuario_osiris, contrasena_osiris, contrasena_macro)

    def log_seguro(mensaje: str) -> None:
        log(_redactar(str(mensaje), secretos))

    def correr_paso(
        nombre: str,
        funcion: Callable[..., Result],
        *args: Any,
    ) -> Result:
        log_seguro(f"Iniciando: {nombre}")

        def progreso_seguro(actual: int, total: int, mensaje: str) -> None:
            progreso(nombre, actual, total, _redactar(str(mensaje), secretos))

        try:
            resultado = funcion(
                *args,
                log=log_seguro,
                progreso=progreso_seguro,
            )
        except Exception as error:
            detalle = _redactar(str(error), secretos).strip() or type(error).__name__
            mensaje = f"Fallo en '{nombre}': {detalle}"
            log_seguro(mensaje)
            raise GenerationError(mensaje) from None

        log_seguro(f"Terminado: {nombre}")
        return resultado

    correr_paso(
        "Descarga de Ts",
        descargar_ts,
        params,
        usuario_osiris,
        contrasena_osiris,
        True,
    )

    if not params.es_ley100:
        correr_paso(
            "Evidencias SOX",
            evidencias.capturar_evidencias_sox,
            params,
            usuario_osiris,
            contrasena_osiris,
        )

    correr_paso(
        "Conversion de CSV a XLSX",
        evidencias.convertir_csv_a_xlsx,
        params.clave_periodo,
    )

    if not params.es_ley100:
        correr_paso(
            "Integridad y Exactitud",
            evidencias.generar_integridad_y_exactitud,
            params.clave_periodo,
        )

    headers, rows, _ = correr_paso(
        "Consolidacion en Excel",
        consolidacion.consolidar,
        params,
        contrasena_macro,
        True,
    )
    stock, nuevo = correr_paso(
        "Generacion de Stock y Nuevo",
        split_stock_nuevo.generar_ts_consolidadas,
        headers,
        rows,
        params,
    )
    return GeneratedFiles(stock=stock, nuevo=nuevo)
