@echo off
setlocal
cd /d "%~dp0"
title Gestor de informes de incidentes TI
where python >nul 2>&1
if not errorlevel 1 (
    python scripts\iniciar.py
    goto fin
)
where py >nul 2>&1
if not errorlevel 1 (
    py -3 scripts\iniciar.py
    goto fin
)
echo No se encontro Python. Instala Python 3.11 o superior y activa Add Python to PATH.
:fin
pause
