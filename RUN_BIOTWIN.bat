@echo off
setlocal
cd /d "%~dp0"
if not exist "serve.py" (echo ERROR: Open the project folder containing serve.py & pause & exit /b 1)
set "PYTHON=py"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"
echo BioTwin is starting. Open http://localhost:8000 in a browser.
"%PYTHON%" serve.py
pause
