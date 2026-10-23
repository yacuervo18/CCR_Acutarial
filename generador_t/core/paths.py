"""Rutas de archivos y carpetas usadas en todo el proceso de cierre.

Todo lo de una corrida queda organizado por ramo y por mes:

    ARL/202608/
        1_Ts_descargadas/            T1..T11 (csv y xlsx) tal como vienen de Osiris
        2_Pantallazos_parametros/    pantallazo de los parametros de cada T
        3_Pantallazos_evidencia/     evidencias SOX arriba/abajo (solo ARL)
        4_Ts_integridad/             T1..T11 con hoja Integridad y Exactitud (solo ARL)
        5_Macro_consolidada/         copia de la macro ya calculada
        6_Ts_consolidadas/           {mes}_t_consolidada_RM.csv (total), _Stock_RM.csv, _Nuevo_RM.csv y manifest.json
        logs/                        detalle de cada corrida (panel de seguimiento)
    Ley100/202608/
        (misma estructura; sin 3 y 4, y archivos con sufijo _Ley100)

Las funciones reciben la "clave del periodo" ("ARL/202608", "Ley100/202608"),
que arma Params.clave_periodo.
"""
from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# tipo_ramo -> (carpeta del ramo, sufijo de las Ts consolidadas)
CARPETA_RAMO = {"ARL": "ARL", "LEY100": "Ley100"}
SUFIJO_CONSOLIDADAS = {"ARL": "RM", "Ley100": "Ley100"}


def clave_periodo(tipo_ramo: str, mes: str) -> str:
    """'ARL' + '202608' -> 'ARL/202608'."""
    return f"{CARPETA_RAMO[tipo_ramo]}/{mes}"


def _partes(clave: str) -> tuple[str, str]:
    carpeta_ramo, mes = clave.split("/")
    return carpeta_ramo, mes


def periodo_dir(clave: str) -> Path:
    return BASE_DIR / clave


def ramo_dir(tipo_ramo: str) -> Path:
    return BASE_DIR / CARPETA_RAMO[tipo_ramo]


def meses_con_datos(tipo_ramo: str) -> list[str]:
    """Meses (YYYYMM) que ya tienen carpeta para el ramo, del mas reciente al mas viejo."""
    d = ramo_dir(tipo_ramo)
    if not d.exists():
        return []
    return sorted((p.name for p in d.iterdir() if p.is_dir() and p.name.isdigit() and len(p.name) == 6), reverse=True)


def ts_mod_dir(clave: str) -> Path:
    """Ts crudas descargadas de Osiris (T1..T11) en csv, y su conversion a xlsx."""
    return periodo_dir(clave) / "1_Ts_descargadas"


def imagenes_parametros_dir(clave: str) -> Path:
    """Pantallazos de los parametros de consulta usados al descargar cada T."""
    return periodo_dir(clave) / "2_Pantallazos_parametros"


def imagenes_evidencia_dir(clave: str) -> Path:
    """Pantallazos de evidencia SOX (vista de datos) de cada T."""
    return periodo_dir(clave) / "3_Pantallazos_evidencia"


def archivos_t_final_dir(clave: str) -> Path:
    """T{n}.xlsx finales con hoja 'Integridad y Exactitud'."""
    return periodo_dir(clave) / "4_Ts_integridad"


def macro_copia_path(clave: str) -> Path:
    """Copia de la macro ya calculada (la plantilla original nunca se sobreescribe)."""
    carpeta_ramo, mes = _partes(clave)
    return periodo_dir(clave) / "5_Macro_consolidada" / f"Macro_consolidacion_{carpeta_ramo}_{mes}.xlsm"


def consolidadas_dir(clave: str) -> Path:
    return periodo_dir(clave) / "6_Ts_consolidadas"


def consolidada_csv_path(clave: str, tipo: str) -> Path:
    """tipo: 'Stock' o 'Nuevo'. Ej: ARL/202608/6_Ts_consolidadas/202608_t_consolidada_Stock_RM.csv"""
    carpeta_ramo, mes = _partes(clave)
    sufijo = SUFIJO_CONSOLIDADAS[carpeta_ramo]
    return consolidadas_dir(clave) / f"{mes}_t_consolidada_{tipo}_{sufijo}.csv"


def consolidada_stock_completo_path(clave: str) -> Path:
    """Stock completo de evidencia cuando el Stock operativo se genera vacio."""
    carpeta_ramo, mes = _partes(clave)
    sufijo = SUFIJO_CONSOLIDADAS[carpeta_ramo]
    return consolidadas_dir(clave) / f"{mes}_t_consolidada_Stock_completo_{sufijo}.csv"


def consolidada_total_path(clave: str) -> Path:
    """Consolidado total (antes de partir en Stock y Nuevo). Ej: Ley100/202608/6_Ts_consolidadas/202608_t_consolidada_Ley100.csv"""
    carpeta_ramo, mes = _partes(clave)
    sufijo = SUFIJO_CONSOLIDADAS[carpeta_ramo]
    return consolidadas_dir(clave) / f"{mes}_t_consolidada_{sufijo}.csv"


def consolidada_revisada_path(clave: str, run_id: str) -> Path:
    """Copia revisada del consolidado total para una corrida concreta."""
    carpeta_ramo, mes = _partes(clave)
    if carpeta_ramo != "Ley100":
        raise ValueError("La revisión de pólizas solo está habilitada para Ley 100.")
    if not run_id.isalnum() or len(run_id) != 32:
        raise ValueError("El identificador de corrida no es válido.")
    return consolidadas_dir(clave) / f"{mes}_t_consolidada_Ley100_revisado_{run_id}.csv"


def correcciones_path(clave: str, run_id: str) -> Path:
    """Bitácora de cambios de póliza para una corrida concreta."""
    carpeta_ramo, mes = _partes(clave)
    if carpeta_ramo != "Ley100":
        raise ValueError("La revisión de pólizas solo está habilitada para Ley 100.")
    if not run_id.isalnum() or len(run_id) != 32:
        raise ValueError("El identificador de corrida no es válido.")
    return consolidadas_dir(clave) / f"{mes}_correcciones_{run_id}.jsonl"


def manifest_path(clave: str) -> Path:
    """Registro de la corrida (parametros y conteos), junto a las Ts consolidadas."""
    return consolidadas_dir(clave) / "manifest.json"


def logs_dir(clave: str) -> Path:
    return periodo_dir(clave) / "logs"


def tasas_ley100_path() -> Path:
    """Excel con la tasa correcta de algunas polizas de Ley 100 (columnas
    'Poliza' y 'POINTERES_TECNICO'); se aplica despues de correr la macro."""
    return BASE_DIR / "Ley100" / "Tasas_cierre.xlsx"


def plantilla_path() -> Path:
    return BASE_DIR / "archivos_T" / "plantilla.xlsx"


def macro_path() -> Path:
    return BASE_DIR / "Macro_consolidacion.xlsm"


def asegurar_directorio(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
