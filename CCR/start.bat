@echo off
chcp 65001 >nul
title CCR - Centro de Control de Reservas y Cierres Actuariales

echo ============================================================
echo  CCR - Centro de Control de Reservas y Cierres Actuariales
echo ============================================================
echo.

REM Verificar Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python no esta instalado o no esta en el PATH.
    echo Por favor instale Python 3.10+ desde https://python.org
    pause
    exit /b 1
)

echo Python detectado:
python --version
echo.

REM Directorio del script
cd /d "%~dp0"

REM Crear entorno virtual si no existe
if not exist ".venv" (
    echo Creando entorno virtual...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo ERROR: No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    echo Entorno virtual creado.
) else (
    echo Entorno virtual ya existe.
)
echo.

REM Activar entorno virtual e instalar dependencias
echo Instalando/actualizando dependencias...
call .venv\Scripts\activate.bat
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Fallo al instalar dependencias.
    pause
    exit /b 1
)
echo Dependencias listas.
echo.

REM Inicializar base de datos si no existe (seed.py se encarga)
echo Verificando base de datos...
python -c "from src.database.seed import init_db; init_db()" 2>&1
if %errorlevel% neq 0 (
    echo ADVERTENCIA: Hubo un problema inicializando la base de datos.
)
echo.

echo Iniciando CCR...
echo ============================================================
streamlit run app.py