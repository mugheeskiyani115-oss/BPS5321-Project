@echo off
setlocal
cd /d "%~dp0"
if not exist "serve.py" (
  echo ERROR: Put the contents of this ZIP next to serve.py in BPS5321-Project-ui-changes.
  pause
  exit /b 1
)
if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=py"
)
echo.
echo === Applying BioTwin commercial finance upgrade to THIS project ===
"%PY%" "_commercial_patch\install_into_existing_project.py" "."
if errorlevel 1 (
  echo.
  echo Installation stopped safely. No existing project files were changed.
  echo Read COMMERCIAL_UPGRADE_README.md for details.
  pause
  exit /b 1
)
echo.
echo === Installing required Python packages ===
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Could not install dependencies. Check your Python environment or network.
  pause
  exit /b 1
)
echo.
echo === Testing financial model ===
"%PY%" -m pytest -q tests\test_commercial_finance_upgrade.py
if errorlevel 1 (
  echo Finance checks did not pass. Do not use export results until resolved.
  pause
  exit /b 1
)
echo.
echo === Starting BioTwin on http://localhost:8000 ===
"%PY%" serve.py
pause
