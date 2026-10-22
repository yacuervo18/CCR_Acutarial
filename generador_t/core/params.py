"""Parametros del cierre (reemplaza al antiguo config.py).

Los parametros se guardan en params.json en la raiz del proyecto para que la
interfaz de Streamlit pueda leerlos y modificarlos sin tocar codigo. Cada ramo
(ARL, LEY100) guarda su propio juego de parametros:

    {"ramo_activo": "ARL", "ARL": {...}, "LEY100": {...}}

Un params.json viejo (plano, sin secciones) se interpreta como el de ARL.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PARAMS_FILE = BASE_DIR / "params.json"

TIPOS_RAMO = ("ARL", "LEY100")

# Valores iniciales de cada ramo la primera vez que se usa (luego se editan
# desde la app y quedan en params.json).
DEFAULTS_POR_RAMO = {
    "ARL": {"ramo": "094", "compania": "22", "fecha_minima_prod_nueva": "202301",
            "fecha_corte_vigencia": date(2023, 1, 1), "stock_vacia": False, "nuevo_vacia": False},
    # LEY100: por defecto Stock = antes de agosto 2024 y Nuevo = desde 20240801.
    "LEY100": {"ramo": "087", "compania": "02", "fecha_minima_prod_nueva": "202408",
               "fecha_corte_vigencia": date(2024, 8, 1), "stock_vacia": False, "nuevo_vacia": False},
}


@dataclass
class Params:
    fecha_valoracion: date
    # YYYYMM: fecha minima de la "nueva produccion" (T11) y tambien el corte
    # que separa Stock (antes de esta fecha) de Nuevo (desde esta fecha).
    fecha_minima_prod_nueva: str = "202301"
    inflacion: float = 6.14
    smmlv: float = 1750905
    interes_real: float = 4.0
    ramo: str = "094"
    compania: str = "22"
    # "ARL" (proceso completo con evidencias SOX) o "LEY100" (solo descarga,
    # macro y Ts consolidadas).
    tipo_ramo: str = "ARL"
    # Filtro de las Ts consolidadas (lo elige el usuario, en ambos ramos):
    # Stock = FEVIGENCIA_INICIAL antes del corte; Nuevo = desde el corte.
    # Cualquiera de las dos se puede dejar vacia (solo columnas).
    fecha_corte_vigencia: date | None = None
    stock_vacia: bool = False
    nuevo_vacia: bool = False

    def __post_init__(self):
        if self.fecha_corte_vigencia is None:
            self.fecha_corte_vigencia = date(
                int(self.fecha_minima_prod_nueva[:4]), int(self.fecha_minima_prod_nueva[4:6]), 1
            )

    @property
    def es_ley100(self) -> bool:
        return self.tipo_ramo == "LEY100"

    @property
    def fecha_valoracion_input(self) -> str:
        """YYYYMM del cierre, tal como se escribe en los formularios de Osiris."""
        return self.fecha_valoracion.strftime("%Y%m")

    @property
    def clave_periodo(self) -> str:
        """Carpeta del periodo dentro del proyecto: 'ARL/202608' o 'Ley100/202608'
        (todo lo de la corrida queda ahi, ver core/paths.py)."""
        from .paths import clave_periodo

        return clave_periodo(self.tipo_ramo, self.fecha_valoracion_input)

    @property
    def encoding_consolidada(self) -> str:
        """El motor de Ley100 (motor_Ley100_RIA) lee las Ts consolidadas en latin-1."""
        return "latin-1" if self.es_ley100 else "utf-8"

    @property
    def fecha_calculo(self) -> date:
        """Primer dia del mes siguiente al cierre (celda 'Fecha de Calculo' de la macro)."""
        if self.fecha_valoracion.month == 12:
            return date(self.fecha_valoracion.year + 1, 1, 1)
        return date(self.fecha_valoracion.year, self.fecha_valoracion.month + 1, 1)

    @property
    def cutoff_stock_nuevo(self) -> date:
        """Fecha de inicio de vigencia que separa Stock de Nuevo."""
        return self.fecha_corte_vigencia

    def to_dict(self) -> dict:
        d = asdict(self)
        d["fecha_valoracion"] = self.fecha_valoracion.isoformat()
        d["fecha_corte_vigencia"] = self.fecha_corte_vigencia.isoformat()
        del d["tipo_ramo"]  # va implicito en la seccion de params.json
        return d

    @classmethod
    def from_dict(cls, d: dict, tipo_ramo: str = "ARL") -> "Params":
        d = dict(d)
        d.pop("tipo_ramo", None)
        d["fecha_valoracion"] = date.fromisoformat(d["fecha_valoracion"])
        if d.get("fecha_corte_vigencia"):
            d["fecha_corte_vigencia"] = date.fromisoformat(d["fecha_corte_vigencia"])
        # params.json de antes del filtro configurable: se completa con lo de
        # siempre de cada ramo (ARL filtra ambas; LEY100 Stock vacia).
        for k in ("stock_vacia", "nuevo_vacia"):
            d.setdefault(k, DEFAULTS_POR_RAMO[tipo_ramo][k])
        return cls(tipo_ramo=tipo_ramo, **d)

    @staticmethod
    def _leer_archivo(path: Path) -> dict:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        if "ramo_activo" not in data:
            # formato viejo (plano): era el de ARL
            data = {"ramo_activo": "ARL", "ARL": data}
        return data

    def save(self, path: Path = PARAMS_FILE) -> None:
        data = self._leer_archivo(path)
        data["ramo_activo"] = self.tipo_ramo
        data[self.tipo_ramo] = self.to_dict()
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, tipo_ramo: str | None = None, path: Path = PARAMS_FILE) -> "Params":
        """Carga los parametros del ramo indicado (o del ultimo usado)."""
        data = cls._leer_archivo(path)
        tipo = tipo_ramo or data.get("ramo_activo", "ARL")
        if tipo in data:
            return cls.from_dict(data[tipo], tipo)
        # Primera vez con este ramo: parte de los valores de mercado del otro
        # ramo (fecha, inflacion, SMMLV, interes) y de los defaults propios.
        base = next((data[t] for t in TIPOS_RAMO if t in data), None)
        p = cls.from_dict(base, tipo) if base else cls(fecha_valoracion=date(2026, 8, 31), tipo_ramo=tipo)
        for k, v in DEFAULTS_POR_RAMO[tipo].items():
            setattr(p, k, v)
        return p
