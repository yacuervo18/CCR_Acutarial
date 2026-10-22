"""Descarga de las Ts (T1..T10) y la nueva produccion (T11) desde Osiris.

Refactor de los antiguos descarga_reserva_matematica.py + Automatizador_Ts.py +
web_scraper.py: misma logica de selenium (probada y funcionando), pero
parametrizada (nada de fechas/ramo/credenciales quemadas en el codigo) y sin
las funciones muertas de navegacion por tabs que ya no se usaban.
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from selenium import webdriver
from selenium.common.exceptions import (
    ElementNotInteractableException,
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from . import paths
from .params import Params

LinkParams = Dict[str, Tuple[str, str]]
Logger = Callable[[str], None]
# progreso(actual, total, texto): avance del paso para la barra de la app.
Progreso = Callable[[int, int, str], None]


def _sin_progreso(actual: int, total: int, texto: str) -> None:
    pass

LINKS_T1_A_T10 = [
    f"https://admriesgo.suranet.com/osiris/servlet/suramericana.rentasv.generico.consultas.Consulta?NMCONSULTA=CCN{n:02d}"
    for n in range(1, 11)
]
LINK_NUEVA_PRODUCCION = (
    "https://admriesgo.suranet.com/osiris/servlet/suramericana.rentasv.generico.consultas.Consulta?NMCONSULTA=CGN01"
)

XPATH_FECHA_CORTE = '/html/body/form/table[1]/tbody/tr[3]/td[2]/div/input'
XPATH_RAMO = '/html/body/form/table[1]/tbody/tr[7]/td[2]/div/input'
XPATH_COMPANIA = '/html/body/form/table[1]/tbody/tr[8]/td[2]/div/input'
XPATH_ESTADO = '/html/body/form/table[1]/tbody/tr[11]/td[2]/div/input'

XPATH_NP_FECHA_INICIO = '/html/body/form/table[1]/tbody/tr[3]/td[2]/div/input'
XPATH_NP_RAMO = '/html/body/form/table[1]/tbody/tr[5]/td[2]/div/input'
XPATH_NP_COMPANIA = '/html/body/form/table[1]/tbody/tr[6]/td[2]/div/input'
XPATH_NP_FECHA_FIN = '/html/body/form/table[1]/tbody/tr[4]/td[2]/div/input'

# (xpath del select, indice 0-based de la opcion). Equivale a los antiguos
# xpaths .../select/option[4] y .../select/option[2].
DROPDOWN_OPTIONS = [
    ('/html/body/form/table[2]/tbody/tr[2]/td[2]/select', 3),
    ('/html/body/form/table[2]/tbody/tr[3]/td[2]/select', 1),
]
XPATH_BOTON_DESCARGAR = '/html/body/form/table[3]/tbody/tr/td/div/a[2]/img'
XPATH_USERNAME = '//*[@id="username"]'
XPATH_PASSWORD = '//*[@id="password"]'
XPATH_BOTON_LOGIN = '//*[@id="lower"]/button'
DOMINIO_OSIRIS = 'admriesgo.suranet.com'
ESPERA_MFA_MAX = 180  # segundos para aprobar el MFA en el celular

# Espera de cada archivo descargado. No hay un limite fijo corto: T8 es muy
# pesada y Osiris puede tardar varios minutos en generarla. Solo se falla si
# Osiris nunca empieza a mandar el archivo, si la descarga se queda quieta
# (el .crdownload deja de crecer) o si se pasa del maximo total.
ESPERA_INICIO_MAX = 20 * 60      # Osiris generando el archivo
ESPERA_SIN_AVANCE_MAX = 5 * 60   # descarga en curso que dejo de crecer
ESPERA_TOTAL_MAX = 60 * 60
NOMBRE_DESCARGA = "consulta_dinamica.csv"


def crear_chrome_driver(carpeta_descarga: Optional[Path] = None) -> webdriver.Chrome:
    from webdriver_manager.chrome import ChromeDriverManager

    options = Options()
    prefs = {
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    if carpeta_descarga is not None:
        # Carpeta propia del proceso en vez de "Descargas" del usuario (que en
        # equipos con OneDrive puede estar redirigida a otra ruta).
        prefs["download.default_directory"] = str(carpeta_descarga)
    options.add_experimental_option("prefs", prefs)
    options.add_experimental_option("detach", True)
    options.add_argument("--start-maximized")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


# Los helpers esperan a que el elemento sea visible/clickeable (no solo que
# exista en el html): en equipos mas lentos o con Chrome mas nuevo, escribir
# en un campo que aun no esta listo da "element not interactable". Si aun asi
# falla, se hace por JavaScript.

def _get_element(driver, locator, timeout: int = 20):
    element = WebDriverWait(driver, timeout).until(EC.presence_of_element_located(locator))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    return element


def _click(driver, locator, timeout: int = 20) -> None:
    element = _get_element(driver, locator, timeout)
    try:
        WebDriverWait(driver, timeout).until(EC.element_to_be_clickable(locator)).click()
    except (ElementNotInteractableException, TimeoutException):
        driver.execute_script("arguments[0].click();", element)


def _send_keys(driver, locator, keys, timeout: int = 20) -> None:
    element = _get_element(driver, locator, timeout)
    try:
        element = WebDriverWait(driver, timeout).until(EC.visibility_of_element_located(locator))
        element.clear()
        element.send_keys(keys)
    except (ElementNotInteractableException, TimeoutException):
        driver.execute_script(
            "arguments[0].value = arguments[1];"
            "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));"
            "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
            element,
            keys,
        )


def _seleccionar(driver, select_xpath: str, indice: int, timeout: int = 20) -> None:
    element = _get_element(driver, (By.XPATH, select_xpath), timeout)
    Select(element).select_by_index(indice)


def _esperar_osiris(driver, log: Logger) -> None:
    """Tras el login, espera a que se apruebe el MFA y la pagina vuelva a
    Osiris (antes eran 10s fijos y solo si la url era exactamente la del MFA:
    si tardaba mas, se intentaba llenar el formulario sobre la pagina del MFA)."""
    if DOMINIO_OSIRIS in driver.current_url:
        return
    log(f"Esperando validacion MFA (aprueba en el celular; maximo {ESPERA_MFA_MAX}s)...")
    try:
        WebDriverWait(driver, ESPERA_MFA_MAX, poll_frequency=1).until(
            lambda d: DOMINIO_OSIRIS in d.current_url
        )
    except TimeoutException:
        raise TimeoutException(
            f"No se volvio a Osiris despues de {ESPERA_MFA_MAX}s (url actual: {driver.current_url}). "
            "Revisa que se haya aprobado el MFA y que usuario/contrasena sean correctos."
        )
    log("MFA validado.")


def _crear_directorio_ts(fecha_cierre: str) -> None:
    paths.asegurar_directorio(paths.ts_mod_dir(fecha_cierre))


def _pantallazo_parametros(driver, num_t: Optional[int], fecha_cierre: str) -> None:
    carpeta = paths.imagenes_parametros_dir(fecha_cierre)
    paths.asegurar_directorio(carpeta)
    nombre = f"t{num_t}_sox_parametros.png" if num_t is not None else "nueva_prod_sox_parametros.png"
    driver.implicitly_wait(15)
    driver.maximize_window()
    driver.save_screenshot(str(carpeta / nombre))


def _carpeta_descarga(fecha_cierre: str) -> Path:
    return paths.ts_mod_dir(fecha_cierre) / "_descarga_en_curso"


def _limpiar_carpeta_descarga(carpeta: Path) -> None:
    """Borra restos de una descarga anterior para no confundir archivos."""
    carpeta.mkdir(parents=True, exist_ok=True)
    for f in carpeta.iterdir():
        if f.is_file() and f.name.startswith("consulta_dinamica"):
            try:
                f.unlink()
            except OSError:
                pass


def _fmt_tiempo(segundos: float) -> str:
    m, s = divmod(int(segundos), 60)
    return f"{m}m {s:02d}s" if m else f"{s}s"


def _esperar_archivo(carpeta: Path, etiqueta: str, log: Logger) -> Path:
    """Espera a que Chrome termine de bajar consulta_dinamica.csv en carpeta.

    Mientras Osiris genera el archivo no hay nada en disco; cuando empieza a
    llegar aparece un .crdownload que va creciendo. Se reporta el avance cada
    15s para que se vea en el seguimiento (T8 puede tardar bastante)."""
    archivo = carpeta / NOMBRE_DESCARGA
    inicio = ultimo_avance = time.time()
    ultimo_tamano = -1
    ultimo_reporte = 0.0
    while True:
        parciales = list(carpeta.glob("*.crdownload"))
        if archivo.exists() and not parciales:
            return archivo
        ahora = time.time()
        transcurrido = ahora - inicio
        tamano = sum(f.stat().st_size for f in parciales if f.exists())
        if parciales and tamano != ultimo_tamano:
            ultimo_tamano, ultimo_avance = tamano, ahora

        if ahora - ultimo_reporte >= 15:
            ultimo_reporte = ahora
            if parciales:
                log(f"{etiqueta}: descargando... {tamano / 1e6:.1f} MB ({_fmt_tiempo(transcurrido)})")
            else:
                log(f"{etiqueta}: Osiris generando el archivo, esperando que empiece la descarga ({_fmt_tiempo(transcurrido)})")

        if not parciales and transcurrido > ESPERA_INICIO_MAX:
            raise TimeoutError(
                f"{etiqueta}: Osiris no empezo a mandar el archivo despues de {_fmt_tiempo(transcurrido)} "
                f"(se esperaba en {carpeta})."
            )
        if parciales and ahora - ultimo_avance > ESPERA_SIN_AVANCE_MAX:
            raise TimeoutError(
                f"{etiqueta}: la descarga se quedo quieta en {tamano / 1e6:.1f} MB por mas de "
                f"{_fmt_tiempo(ESPERA_SIN_AVANCE_MAX)}. Revisa la conexion/VPN y vuelve a intentar."
            )
        if transcurrido > ESPERA_TOTAL_MAX:
            raise TimeoutError(f"{etiqueta}: la descarga paso de {_fmt_tiempo(ESPERA_TOTAL_MAX)}.")
        time.sleep(2)


def _mover_descarga(
    num_t: Optional[int], fecha_cierre: str, modo: str, log: Logger = print,
    carpeta: Optional[Path] = None,
) -> None:
    carpeta = carpeta or _carpeta_descarga(fecha_cierre)
    nuevo_nombre = f"T{num_t}.csv" if modo == "T" else "T11.csv"
    destino_dir = paths.ts_mod_dir(fecha_cierre)

    log(f"T{num_t}: esperando que termine la descarga del archivo...")
    original_path = _esperar_archivo(carpeta, f"T{num_t}", log)
    log(f"T{num_t}: descarga completa ({original_path.stat().st_size / 1e6:.1f} MB).")

    destino_final = destino_dir / nuevo_nombre
    if destino_final.exists():
        destino_final.unlink()
    shutil.move(str(original_path), str(destino_final))
    log(f"T{num_t}: archivo guardado como {destino_final.name}.")


def _procesar_link(
    driver,
    fecha_cierre: str,
    link: str,
    file_suffix: Optional[int],
    form_data: LinkParams,
    usuario: str,
    contrasena: str,
    log: Logger,
    carpeta_descarga: Optional[Path] = None,
) -> None:
    carpeta_descarga = carpeta_descarga or _carpeta_descarga(fecha_cierre)
    _limpiar_carpeta_descarga(carpeta_descarga)
    paso = "abrir pagina"
    try:
        driver.get(link)
        time.sleep(1.5)

        page = driver.page_source.lower()
        if "username" in page and "password" in page:
            paso = "login"
            log("Iniciando sesion...")
            _send_keys(driver, (By.XPATH, XPATH_USERNAME), usuario)
            _send_keys(driver, (By.XPATH, XPATH_PASSWORD), contrasena)
            _click(driver, (By.XPATH, XPATH_BOTON_LOGIN))
            time.sleep(1.5)
            paso = "MFA"
            _esperar_osiris(driver, log)
            # Si el SSO no devolvio a la consulta pedida, se vuelve a abrir.
            if driver.current_url.split("?")[0] != link.split("?")[0]:
                driver.get(link)
                time.sleep(1.5)

        log(f"T{file_suffix}: llenando parametros ({', '.join(f'{k}={v}' for k, (_, v) in form_data.items())})...")
        for nombre_campo, (xpath, valor) in form_data.items():
            paso = f"campo {nombre_campo}"
            _send_keys(driver, (By.XPATH, xpath), valor)

        for n, (select_xpath, indice) in enumerate(DROPDOWN_OPTIONS, start=1):
            paso = f"lista desplegable {n}"
            _seleccionar(driver, select_xpath, indice)

        paso = "boton descargar"
        log(f"T{file_suffix}: descargando...")
        _click(driver, (By.XPATH, XPATH_BOTON_DESCARGAR))

        _pantallazo_parametros(driver, file_suffix, fecha_cierre)

        paso = "esperar archivo descargado"
        modo = "T" if link[-5:] != "CGN01" else "NP"
        _mover_descarga(file_suffix, fecha_cierre, modo, log, carpeta_descarga)

    except (TimeoutException, NoSuchElementException, ElementNotInteractableException) as e:
        # El mensaje de selenium no dice en que parte del formulario fallo.
        detalle = getattr(e, "msg", None) or str(e)
        log(f"Fallo en el paso '{paso}' de {link}: {detalle}")
        raise RuntimeError(f"Fallo en el paso '{paso}' ({type(e).__name__}): {detalle}") from e


def construir_parametros(params: Params) -> Tuple[LinkParams, LinkParams]:
    fecha_cierre = params.fecha_valoracion_input
    parametros_t = {
        "FECHA_CORTE": (XPATH_FECHA_CORTE, fecha_cierre),
        "RAMO": (XPATH_RAMO, params.ramo),
        "COMPAÑIA": (XPATH_COMPANIA, params.compania),
        "ESTADO": (XPATH_ESTADO, "P"),
    }
    parametros_nueva_prod = {
        "FECHA_INICIO": (XPATH_NP_FECHA_INICIO, params.fecha_minima_prod_nueva),
        "RAMO": (XPATH_NP_RAMO, params.ramo),
        "COMPAÑIA": (XPATH_NP_COMPANIA, params.compania),
        "FECHA_FIN": (XPATH_NP_FECHA_FIN, fecha_cierre),
    }
    return parametros_t, parametros_nueva_prod


def descargar_ts(
    params: Params,
    usuario: str,
    contrasena: str,
    incluir_nueva_produccion: bool = True,
    driver: Optional[webdriver.Chrome] = None,
    log: Logger = print,
    progreso: Progreso = _sin_progreso,
) -> None:
    """Descarga T1..T10 (y T11/nueva produccion si se indica) para el cierre dado.

    Requiere credenciales de Osiris/SURA pasadas en tiempo de ejecucion (no se
    guardan en disco). Crea/usa un Chrome driver propio si no se pasa uno.
    """
    # Los formularios de Osiris llevan el YYYYMM del cierre; las carpetas
    # locales usan la clave del periodo (con sufijo _LEY100 si aplica).
    fecha_cierre = params.clave_periodo
    parametros_t, parametros_np = construir_parametros(params)

    links = list(LINKS_T1_A_T10)
    if incluir_nueva_produccion:
        links.append(LINK_NUEVA_PRODUCCION)

    _crear_directorio_ts(fecha_cierre)

    total = len(links)
    propio = driver is None
    # Con Chrome propio se descarga a una carpeta del proceso; si nos pasan
    # un driver ya abierto, sus descargas caen en "Descargas" del usuario.
    carpeta_descarga = _carpeta_descarga(fecha_cierre) if propio else Path.home() / "Downloads"
    if propio:
        progreso(0, total, "Abriendo Chrome...")
        log("Abriendo Chrome...")
        carpeta_descarga.mkdir(parents=True, exist_ok=True)
        driver = crear_chrome_driver(carpeta_descarga)

    try:
        for i, link in enumerate(links, start=1):
            es_nueva_prod = link[-5:] == "CGN01"
            # Ojo: aunque sea la nueva produccion, el pantallazo de parametros
            # y el archivo se siguen nombrando con el numero secuencial (T11),
            # nunca con num_t=None (eso solo aplicaria a otro tipo de consulta
            # que este flujo no usa).
            suffix = i
            form_data = parametros_np if es_nueva_prod else parametros_t
            etiqueta = f"T{suffix}" + (" (nueva produccion)" if es_nueva_prod else "")
            progreso(i - 1, total, f"{etiqueta} ({i} de {total})")
            log(f"Procesando {etiqueta} ({i} de {total})...")
            inicio = time.time()
            _procesar_link(
                driver, fecha_cierre, link, suffix, form_data, usuario, contrasena, log, carpeta_descarga
            )
            log(f"{etiqueta} descargada ({_fmt_tiempo(time.time() - inicio)}).")
            progreso(i, total, f"{etiqueta} descargada")
            time.sleep(2)  # ya se espero el archivo real; no hace falta una pausa larga
        log("Descarga de las Ts finalizada con exito.")
    finally:
        if propio:
            driver.quit()
            try:
                carpeta_descarga.rmdir()  # solo si quedo vacia
            except OSError:
                pass
