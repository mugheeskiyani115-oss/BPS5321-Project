@echo off
setlocal
cd /d "%~dp0"
if not exist "serve.py" (
  echo ERROR: Extract the ZIP contents into your BioTwin website project folder containing serve.py.
  pause
  exit /b 1
)
if not exist "api\server.py" (
  echo ERROR: This is not the FastAPI/JavaScript BioTwin version.
  pause
  exit /b 1
)
set "PYTHON=py"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"
echo.
echo == Applying BioTwin financial controls and reconciliation ==
"%PYTHON%" "_biotwin_finance_update\install_into_repo.py" "."
if errorlevel 1 (
  echo Upgrade safely stopped. No partial installation should have occurred.
  pause
  exit /b 1
)
echo.
echo == Checking Python source ==
"%PYTHON%" -m compileall -q biotwin api
if errorlevel 1 (
  echo Syntax check failed. Check the error above.
  pause
  exit /b 1
)
echo.
echo == Starting BioTwin at http://localhost:8000 ==
"%PYTHON%" serve.py
pause
