"""Shared identifiers and safe dispatch contract for process operations."""

from dataclasses import dataclass
import re
import unicodedata
from typing import Callable, Literal


@dataclass(frozen=True)
class ProcessOperation:
    identifier: str
    process_code: str
    label: str
    aliases: tuple[str, ...]
    confirmation_prompt: str
    unavailable_message: str
    requestable: bool = True
    requires_review: bool = False


@dataclass(frozen=True)
class OperationResult:
    status: Literal["completed", "unavailable", "cancelled"]
    message: str


PROCESS_OPERATIONS = (
    ProcessOperation(
        "rentabilidades.actualizar",
        "rentabilidades",
        "Actualizar rentabilidades",
        (
            "actualizar rentabilidades",
            "actualiza rentabilidades",
            "actualizame rentabilidades",
            "actualiza las rentabilidades",
            "actualizame las rentabilidades",
            "actualizame las rentabilidades por favor",
            "quiero actualizar rentabilidades",
            "quiero que actualices rentabilidades",
            "puedes actualizar rentabilidades",
            "puedes actualizar las rentabilidades",
            "por favor actualiza rentabilidades",
        ),
        "La preparación de rentabilidades aún no está implementada. "
        "Confirmar mostrará ese estado; no iniciará scraping ni preparará correo.",
        "Actualizar rentabilidades aún no está implementado; no se ejecutó ninguna acción.",
    ),
    ProcessOperation(
        "rentabilidades.copiar",
        "rentabilidades",
        "Copiar",
        (
            "copiar rentabilidades",
            "copiar la tabla de rentabilidades",
            "copiar el correo de rentabilidades",
            "copiar texto de rentabilidades",
            "quiero copiar rentabilidades",
            "puedes copiar rentabilidades",
        ),
        "La tabla y el texto para copiar aún no están implementados. "
        "Confirmar mostrará ese estado; no copiará ni enviará nada.",
        "La copia de rentabilidades aún no está implementada; no se copió ni envió nada.",
    ),
    ProcessOperation(
        "indices.extraer",
        "indices",
        "Extraer datos",
        (
            "extraer datos",
            "extrae datos",
            "extraer datos de indices",
            "extraer indices y monedas",
            "extraer los indices y monedas",
            "extraer datos de monedas",
            "quiero extraer datos de indices",
            "puedes extraer datos de indices",
        ),
        "La extracción y la tabla revisable aún no están implementadas. "
        "Confirmar mostrará ese estado; no se consultarán fuentes.",
        "La extracción de índices y monedas aún no está implementada; no se consultaron fuentes.",
    ),
    ProcessOperation(
        "indices.actualizar_osiris",
        "indices",
        "Actualizar OSIRIS",
        (
            "actualizar osiris",
            "actualiza osiris",
            "actualizame osiris",
            "quiero actualizar osiris",
            "puedes actualizar osiris",
            "actualizar indices en osiris",
            "actualiza los indices en osiris",
        ),
        "La actualización de OSIRIS aún no está implementada y requiere datos revisados. "
        "Confirmar mostrará ese estado; no se modificará OSIRIS.",
        "La actualización de OSIRIS aún no está implementada; no se modificó ningún dato.",
        requires_review=True,
    ),
    ProcessOperation(
        "indices.actualizar_archivos",
        "indices",
        "Actualizar archivos",
        (
            "actualizar archivos",
            "actualizar archivos de indices y monedas",
            "actualiza archivos de indices",
        ),
        "Esta acción permanece deshabilitada hasta resolver los permisos del agente requerido.",
        "Actualizar archivos está deshabilitado por permisos; no se modificó ningún archivo.",
        requestable=False,
    ),
)

PROCESS_OPERATION_BY_ID = {
    operation.identifier: operation for operation in PROCESS_OPERATIONS
}

PROCESS_OPERATION_HANDLERS: dict[str, Callable[[str], str]] = {}


def _normalizar(texto: str) -> str:
    sin_marcas = unicodedata.normalize("NFKD", texto.casefold())
    sin_acentos = "".join(char for char in sin_marcas if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^\w\s]", " ", sin_acentos).split())


_ALIAS_TO_OPERATION = {
    _normalizar(alias): operation
    for operation in PROCESS_OPERATIONS
    for alias in operation.aliases
}


def reconocer_operacion(texto: str) -> ProcessOperation | None:
    """Recognize only explicit action phrases, not general questions about a process."""
    return _ALIAS_TO_OPERATION.get(_normalizar(texto))


def registrar_manejador_operacion(
    identifier: str,
    handler: Callable[[str], str],
) -> None:
    operation = PROCESS_OPERATION_BY_ID.get(identifier)
    if operation is None:
        raise ValueError("La operación solicitada no está registrada.")
    if not operation.requestable:
        raise ValueError("La operación permanece deshabilitada por sus permisos.")
    if identifier in PROCESS_OPERATION_HANDLERS:
        raise ValueError("La operación ya tiene un manejador registrado.")
    PROCESS_OPERATION_HANDLERS[identifier] = handler


def ejecutar_operacion_confirmada(
    identifier: str,
    period: str,
    *,
    data_reviewed: bool = False,
) -> OperationResult:
    """Dispatch only a registered handler; never pretend a planned operation succeeded."""
    operation = PROCESS_OPERATION_BY_ID.get(identifier)
    if operation is None:
        raise ValueError("La operación solicitada no está registrada.")

    if not operation.requestable:
        return OperationResult("unavailable", operation.unavailable_message)

    if operation.requires_review and not data_reviewed:
        return OperationResult(
            "unavailable",
            f"{operation.label} requiere revisar los datos y una confirmación "
            "adicional. La operación aún no está implementada; no se ejecutó "
            "ninguna acción.",
        )

    handler = PROCESS_OPERATION_HANDLERS.get(identifier)
    if handler is None:
        return OperationResult("unavailable", operation.unavailable_message)

    return OperationResult("completed", handler(period))
