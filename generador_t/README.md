# Generador de stock para RM

Componente independiente en preparación para generar las tablas consolidadas
de Stock y Nuevo requeridas por RM Ley 100 y RM ARL.

## Estado

Esta carpeta contiene una copia aislada del código de referencia y los
archivos de plantilla requeridos. El núcleo cuenta con un orquestador sin
interfaz (`core/runner.py`) y un worker (`core/worker.py`). El Centro de
Control lo inicia como subproceso independiente desde las pantallas RM ARL y
RM Ley 100. No está integrado en el código de cálculo de los motores y sus
archivos de salida no se copian a las carpetas de estos. La interfaz original
de Streamlit no se copió.

La lógica de evidencias SOX de ARL se conserva en `core/evidencias.py`.
Las pruebas simulan los pasos para no acceder a Osiris ni abrir Chrome o Excel;
la validación de una corrida real sigue pendiente.

## Requisitos previstos

- Windows, Chrome y Excel de escritorio instalado.
- Python 3.10 o superior.
- Dependencias listadas en `requirements.txt`.
- Acceso a Osiris y aprobación del MFA durante la descarga.

La automatización de la macro requiere Excel y pywin32. La descarga requiere
Chrome y Selenium. Las credenciales de Osiris no deben guardarse en archivos
ni en el repositorio.

En cada equipo Windows, ejecuta `instalar.bat` una vez para preparar
`generador_t\.venv`. CCR inicia `core.worker` en un proceso separado y le
envía la solicitud por entrada estándar; no se pasan credenciales en los
argumentos del proceso. Se permite una generación a la vez para evitar que dos
corridas compartan Chrome o Excel.

## Pruebas locales

Desde esta carpeta, ejecuta:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

El worker se puede iniciar con `.\.venv\Scripts\python.exe -m core.worker`;
recibe por entrada estándar la solicitud JSON que le entrega CCR y emite
eventos JSON por salida estándar. `core.runner.generar(...)` devuelve las
rutas de Stock y Nuevo dentro de la carpeta propia de este componente.

## Contenido copiado

- `core/`: parámetros, descarga, evidencias SOX, automatización de Excel y
  separación de Stock/Nuevo, orquestación y worker del subproceso.
- `Macro_consolidacion.xlsm`, `archivos_T/plantilla.xlsx` y
  `Ley100/Tasas_cierre.xlsx`: archivos de soporte usados por el proceso.
- `params.json`: parámetros de referencia copiados desde la versión recibida.
- `instalar.bat`: prepara el entorno virtual y sus dependencias en cada PC.

La carpeta original recibida se conserva intacta como referencia hasta que el
componente nuevo esté completo y validado.
