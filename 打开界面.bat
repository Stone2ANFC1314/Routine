@echo off
title Ripple
set "ROOT=A:\Desktop\Work\Routine"
set "PY=%ROOT%\.venv\Scripts\python.exe"

if not exist "%PY%" (
    echo.
    echo [ERROR] Python not found:
    echo   %PY%
    echo.
    echo Make sure .venv exists, or re-run setup.
    pause
    exit /b 1
)

cd /d "%ROOT%\Anigame-script-manager"

REM No "start" here: with start, an error window closes instantly
REM and you never see the reason. Running directly keeps the traceback
REM on screen so you can read it, then press any key to close.
"%PY%" main.py

if errorlevel 1 (
    echo.
    echo ============================================
    echo  The program exited with an error.
    echo  Full log: Anigame-script-manager\startup_error.log
    echo ============================================
    pause
)
