@echo off
cd /d "%~dp0"
title Steam Epic Bridge - Inicializador
echo ===================================================
echo        Inicializando Steam Epic Bridge...
echo ===================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERRO] O Python nao foi encontrado no seu sistema.
    echo Instale o Python 3.10+ em https://www.python.org marcando "Add Python to PATH".
    pause
    exit /b 1
)

echo Verificando dependencias...
python -m pip install -r requirements.txt --quiet --no-warn-script-location

echo.
echo [OK] Iniciando a Interface Grafica...
start "" pythonw SteamEpicBridge.py gui
exit
