@echo off
chcp 65001 >nul
setlocal

title CCR + Motor F394

set "ROOT_DIR=%~dp0"
set "CCR_DIR=%ROOT_DIR%CCR"
set "MOTOR_DIR=%ROOT_DIR%Motor_F394"
set "CCR_PYTHON=%CCR_DIR%\.venv\Scripts\python.exe"
set "MOTOR_PYTHON=%MOTOR_DIR%\.venv\Scripts\python.exe"

echo ============================================================
echo  CCR + Motor F394
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

echo Iniciando CCR en http://localhost:8501...
start "CCR Streamlit" /min /d "%CCR_DIR%" "%CCR_PYTHON%" -m streamlit run app.py --server.headless true --server.port 8501

echo Iniciando Motor F394 en http://127.0.0.1:8502...
start "Motor F394 Streamlit" /min /d "%MOTOR_DIR%" "%MOTOR_PYTHON%" -m streamlit run app.py --server.headless true --server.port 8502

timeout /t 5 /nobreak >nul
start "" http://localhost:8501

echo.
echo CCR y Motor F394 fueron iniciados.
echo CCR:       http://localhost:8501
echo Motor F394: http://127.0.0.1:8502
echo.
echo No cierre las ventanas minimizadas mientras use las aplicaciones.
endlocal
