"""Subprocess entry point; reads its one-time request from stdin."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import msvcrt

from .params import DEFAULTS_POR_RAMO, Params
from .runner import GenerationError, generar

BASE_DIR = Path(__file__).resolve().parents[1]


class GeneratorLock:
    def __init__(self):
        self.path = BASE_DIR / ".run_locks" / "stock-generator.lock"
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a+b")
        self.handle.seek(0, 2)
        if self.handle.tell() == 0:
            self.handle.write(b"\0")
            self.handle.flush()
        self.handle.seek(0)
        try:
            msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self.handle.close()
            self.handle = None
            raise RuntimeError(
                "Ya hay una generación en curso para este ramo y periodo."
            ) from None
        return self

    def __exit__(self, *_: object) -> None:
        if self.handle is not None:
            self.handle.close()
            self.handle = None


def _emit(event_type: str, **fields: Any) -> None:
    event = {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "type": event_type,
        **fields,
    }
    print(json.dumps(event, ensure_ascii=False), flush=True)


def _run(payload: dict[str, Any]) -> int:
    tipo_ramo = payload["tipo_ramo"]
    if tipo_ramo not in {"ARL", "LEY100"}:
        raise ValueError("El ramo solicitado no está admitido.")
    params = Params.from_dict(payload["params"], tipo_ramo)
    defaults = DEFAULTS_POR_RAMO[tipo_ramo]
    if (params.ramo, params.compania) != (
        defaults["ramo"],
        defaults["compania"],
    ):
        raise ValueError("El ramo o la compañía no corresponden al proceso seleccionado.")
    credentials = payload["credentials"]
    if not isinstance(credentials, dict) or any(
        not isinstance(credentials.get(key), str)
        for key in ("usuario_osiris", "contrasena_osiris", "contrasena_macro")
    ):
        raise ValueError("Las credenciales de la solicitud no tienen un formato válido.")
    with GeneratorLock():
        result = generar(
            params,
            credentials["usuario_osiris"],
            credentials["contrasena_osiris"],
            credentials["contrasena_macro"],
            log=lambda message: _emit("log", message=message),
            progreso=lambda step, current, total, message: _emit(
                "progress",
                step=step,
                current=current,
                total=total,
                message=message,
            ),
        )
    _emit(
        "completed",
        stock=str(result.stock),
        nuevo=str(result.nuevo),
    )
    return 0


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError("La solicitud del generador tiene un formato inválido.")
        return _run(payload)
    except GenerationError as error:
        _emit("error", message=str(error))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        _emit("error", message=f"Solicitud inválida: {error}")
    except RuntimeError as error:
        _emit("error", message=str(error))
    except OSError as error:
        _emit("error", message=f"No se pudo iniciar el proceso: {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
