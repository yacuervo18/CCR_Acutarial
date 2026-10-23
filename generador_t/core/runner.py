"""Orquesta la generacion de Stock/Nuevo sin depender de una interfaz."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence, TypeVar

from . import consolidacion, evidencias, paths, split_stock_nuevo
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
    stock: Path | None
    nuevo: Path | None
    total: Path | None = None


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
    revisar_antes_de_partir: bool = False,
) -> GeneratedFiles:
    """Ejecuta el proceso completo y devuelve las rutas de Stock y Nuevo.

    Con revisar_antes_de_partir=True se detiene tras guardar el consolidado
    total (stock y nuevo quedan en None); luego se continua con
    partir_consolidado(), que no necesita credenciales.

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
    if revisar_antes_de_partir:
        total, _ = correr_paso(
            "Consolidado total",
            split_stock_nuevo.generar_consolidado_total,
            headers,
            rows,
            params,
        )
        return GeneratedFiles(stock=None, nuevo=None, total=total)

    stock, nuevo = correr_paso(
        "Generacion de Stock y Nuevo",
        split_stock_nuevo.generar_ts_consolidadas,
        headers,
        rows,
        params,
    )
    return GeneratedFiles(
        stock=stock,
        nuevo=nuevo,
        total=paths.consolidada_total_path(params.clave_periodo),
    )


def partir_consolidado(
    params: Params,
    log: Logger = _sin_log,
    progreso: Progress = _sin_progreso,
) -> GeneratedFiles:
    """Etapa B: parte en Stock y Nuevo el consolidado total ya guardado."""
    log("Iniciando: Generacion de Stock y Nuevo (desde el consolidado total)")

    def progreso_paso(actual: int, total: int, mensaje: str) -> None:
        progreso("Generacion de Stock y Nuevo", actual, total, mensaje)

    try:
        stock, nuevo = split_stock_nuevo.partir_desde_total(params, log=log, progreso=progreso_paso)
    except Exception as error:
        mensaje = f"Fallo en 'Generacion de Stock y Nuevo': {str(error).strip() or type(error).__name__}"
        log(mensaje)
        raise GenerationError(mensaje) from None
    log("Terminado: Generacion de Stock y Nuevo")
    return GeneratedFiles(
        stock=stock,
        nuevo=nuevo,
        total=paths.consolidada_total_path(params.clave_periodo),
    )
