@echo off
setlocal
cd /d "%~dp0"
if not exist "serve.py" (
  echo ERROR: This update must be extracted into the existing BioTwin folder containing serve.py
  echo It must sit alongside api, biotwin, web and data folders.
  pause
  exit /b 1
)
if not exist "api\server.py" (
  echo ERROR: api\server.py not found. Do NOT apply to the old Streamlit app.
  pause
  exit /b 1
)
set "PYTHON=py"
if exist ".venv\Scripts\python.exe" set "PYTHON=.venv\Scripts\python.exe"
echo.
echo === Applying BioTwin PDF and six-sector updates to this exact project ===
"%PYTHON%" "_biotwin_update\install_into_repo.py" "."
if errorlevel 1 (
  echo.
  echo Update stopped safely. Copy the error above and share it for troubleshooting.
  pause
  exit /b 1
)
echo.
echo === Installing PDF and application dependencies ===
"%PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install Python dependencies.
  pause
  exit /b 1
)
echo.
echo === Checking updated Python syntax ===
"%PYTHON%" -m compileall -q api biotwin
if errorlevel 1 (
  echo Python syntax check failed.
  pause
  exit /b 1
)
echo.
echo === Starting BioTwin website ===
echo Open http://localhost:8000 in your browser.
echo Press Ctrl+C to stop the server.
"%PYTHON%" serve.py
pause
