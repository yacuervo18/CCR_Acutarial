@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================================
echo   Preparar generador_t para RM
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: No se encontro Python en PATH.
    echo Instale Python 3.10 o superior y marque "Add python.exe to PATH".
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno virtual aislado...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: No se pudo crear generador_t\.venv.
        pause
        exit /b 1
    )
)

echo Instalando dependencias del generador...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: No se pudieron instalar las dependencias.
    pause
    exit /b 1
)

echo Verificando el punto de entrada...
".venv\Scripts\python.exe" -c "from core.worker import main; from core.runner import generar; print('Generador listo.')"
if errorlevel 1 (
    echo ERROR: El generador no pudo importarse correctamente.
    pause
    exit /b 1
)

echo.
echo Generador preparado. No se inicio Chrome ni Excel.
pause
endlocal
