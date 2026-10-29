@echo off
cd /d "%~dp0"
echo Iniciando Organizar de Informes de Incidentes...
echo Abre http://127.0.0.1:8080 en el navegador.
echo Para cerrar la aplicacion, presiona Ctrl+C.
"%~dp0.venv\Scripts\python.exe" -m flask --app "%~dp0app.py" run --host 127.0.0.1 --port 8080
pause
