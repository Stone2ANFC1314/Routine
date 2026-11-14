@echo off
title вт╪Л
set "ROOT=A:\Desktop\Work\Routine"
set "PY=%ROOT%\.venv\Scripts\python.exe"
cd /d "%ROOT%"
"%PY%" "%ROOT%\tools\selfcheck.py"
echo.
pause
