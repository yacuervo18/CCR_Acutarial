@echo off
chcp 65001 >nul
setlocal

title CCR + Motor F394 + Motores CCR

set "ROOT_DIR=%~dp0"
set "CCR_DIR=%ROOT_DIR%CCR"
set "MOTOR_DIR=%ROOT_DIR%Motor_F394"
set "CCR_PYTHON=%CCR_DIR%\.venv\Scripts\python.exe"
set "MOTOR_PYTHON=%MOTOR_DIR%\.venv\Scripts\python.exe"

echo ============================================================
echo  CCR + Motor F394 + Motores CCR
echo ============================================================
echo.

if not exist "%CCR_PYTHON%" (
    echo ERROR: No se encontro el entorno virtual de CCR:
    echo        %CCR_PYTHON%
    echo.
    echo Ejecute primero CCR\start.bat para preparar CCR.
    pause
    exit /b 1
)

if not exist "%MOTOR_PYTHON%" (
    echo ERROR: No se encontro el entorno virtual de Motor F394:
    echo        %MOTOR_PYTHON%
    echo.
    echo Prepare primero Motor_F394\.venv con sus dependencias.
    pause
    exit /b 1
)

echo Verificando CCR en http://localhost:8501...
curl.exe --silent --fail --max-time 2 http://127.0.0.1:8501/_stcore/health >nul 2>&1
if errorlevel 1 (
    echo Iniciando CCR...
    start "CCR Streamlit" /min /d "%CCR_DIR%" "%CCR_PYTHON%" -m streamlit run app.py --server.headless true --server.port 8501
) else (
    echo CCR ya esta iniciado.
)

echo Verificando Motor F394 en http://127.0.0.1:8502...
curl.exe --silent --fail --max-time 2 http://127.0.0.1:8502/_stcore/health >nul 2>&1
if errorlevel 1 (
    echo Iniciando Motor F394...
    start "Motor F394 Streamlit" /min /d "%MOTOR_DIR%" "%MOTOR_PYTHON%" -m streamlit run app.py --server.headless true --server.port 8502
) else (
    echo Motor F394 ya esta iniciado.
)

set "MOTORES_CCR_DIR=%ROOT_DIR%motores_CCR"
set "MOTORES_CCR_PYTHON=%MOTORES_CCR_DIR%\.venv\Scripts\python.exe"
if not exist "%MOTORES_CCR_PYTHON%" (
    echo AVISO: Motores CCR no se inicia: falta su entorno virtual:
    echo        %MOTORES_CCR_PYTHON%
) else (
    echo Verificando Motores CCR en http://127.0.0.1:8503...
    curl.exe --silent --fail --max-time 2 http://127.0.0.1:8503/_stcore/health >nul 2>&1
    if errorlevel 1 (
        echo Iniciando Motores CCR...
        start "Motores CCR Streamlit" /min /d "%MOTORES_CCR_DIR%" "%MOTORES_CCR_PYTHON%" -m streamlit run app.py --server.headless true --server.port 8503
    ) else (
        echo Motores CCR ya estan iniciados.
    )
)

set "GENERADOR_T_DIR=%ROOT_DIR%generador_t"
set "GENERADOR_T_PYTHON=%GENERADOR_T_DIR%\.venv\Scripts\python.exe"
if not exist "%GENERADOR_T_PYTHON%" (
    echo AVISO: Generar t_consolidada estara deshabilitado hasta ejecutar:
    echo        generador_t\instalar.bat
) else (
    echo Generador de t_consolidada preparado para su ejecucion desde CCR.
)

timeout /t 5 /nobreak >nul
start "" http://localhost:8501

echo.
echo CCR, Motor F394 y Motores CCR estan listos o iniciandose.
echo CCR:       http://localhost:8501
echo Motor F394: http://127.0.0.1:8502
echo Motores CCR (selector Ley 100 / ARL): http://127.0.0.1:8503
echo.
echo No cierre las ventanas minimizadas mientras use las aplicaciones.
endlocal
