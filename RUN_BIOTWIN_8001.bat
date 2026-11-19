@echo off
setlocal

rem Always run from the folder containing this batch file.
cd /d "%~dp0"
title BioTwin Singapore - Local Website

echo ===========================================
echo          BioTwin Singapore Launcher

echo ===========================================
echo.

if not exist "api\server.py" (
    echo ERROR: This batch file must be in the BioTwin project folder.
    echo Put it next to serve.py, api, biotwin and web.
    echo.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: The project's Python environment was not found.
    echo The working command used .venv\Scripts\python.exe.
    echo Make sure the .venv folder is in this project folder.
    echo.
    pause
    exit /b 1
)

set "BIOTWIN_URL=http://127.0.0.1:8001/"
echo Starting BioTwin at %BIOTWIN_URL%
echo The browser will open automatically when the server is ready.
echo Keep this window open while using BioTwin.
echo Press Ctrl+C to stop the server.
echo.

rem Wait until the server really responds before launching the browser.
start "" powershell.exe -NoProfile -WindowStyle Hidden -Command "$u='http://127.0.0.1:8001/'; for ($n=0; $n -lt 45; $n++) { try { $null=Invoke-WebRequest -UseBasicParsing -Uri $u -TimeoutSec 2; Start-Process $u; break } catch { Start-Sleep -Milliseconds 700 } }"

".venv\Scripts\python.exe" -m uvicorn api.server:app --host 127.0.0.1 --port 8001

if errorlevel 1 (
    echo.
    echo BioTwin could not start. If port 8001 is already in use,
    echo the site may already be running at %BIOTWIN_URL%
    echo Read the error above for details.
    pause
)
endlocal
