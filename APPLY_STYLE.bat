@echo off
setlocal EnableExtensions
set "UPGRADE=%~dp0"
for %%I in ("%UPGRADE%..") do set "PROJECT=%%~fI"
echo === BioTwin sustainability PDF styling update ===
if not exist "%PROJECT%\serve.py" (
  echo ERROR: Put this folder next to serve.py in your BioTwin website project.
  pause
  exit /b 1
)
if not exist "%PROJECT%\biotwin\reporting.py" (
  echo ERROR: Existing PDF export not found: biotwin\reporting.py
  echo Install the PDF export feature before changing its style.
  pause
  exit /b 1
)
copy /Y "%PROJECT%\biotwin\reporting.py" "%PROJECT%\biotwin\reporting_before_colour_style.py.bak" >nul
if errorlevel 1 (
  echo ERROR: Could not back up the original generator.
  pause
  exit /b 1
)
copy /Y "%UPGRADE%reporting.py" "%PROJECT%\biotwin\reporting.py" >nul
if errorlevel 1 (
  echo ERROR: Could not replace reporting.py. Check permissions.
  pause
  exit /b 1
)
if exist "%PROJECT%\.venv\Scripts\python.exe" (
  "%PROJECT%\.venv\Scripts\python.exe" -m py_compile "%PROJECT%\biotwin\reporting.py"
) else (
  py -m py_compile "%PROJECT%\biotwin\reporting.py"
)
if errorlevel 1 (
  copy /Y "%PROJECT%\biotwin\reporting_before_colour_style.py.bak" "%PROJECT%\biotwin\reporting.py" >nul
  echo ERROR: Syntax check failed. Previous file restored.
  pause
  exit /b 1
)
echo.
echo SUCCESS: PDF report style updated. The rest of BioTwin is unchanged.
echo Restart BioTwin and export a new PDF after running an evaluation.
pause
endlocal
