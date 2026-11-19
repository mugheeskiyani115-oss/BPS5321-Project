@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title BioTwin Singapore - Local Website

echo ==========================================
echo   BioTwin Singapore - Local Website
echo ==========================================

if not exist "serve.py" (
    echo.
    echo ERROR: serve.py was not found.
    echo Copy this batch file into the BioTwin project folder
    echo alongside serve.py, requirements.txt, web, api and biotwin.
    echo.
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo ERROR: requirements.txt was not found next to serve.py.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating a Python virtual environment for this computer...
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 -m venv .venv
    ) else (
        where python >nul 2>&1
        if errorlevel 1 (
            echo ERROR: Python was not found. Install Python 3 and try again.
            pause
            exit /b 1
        )
        python -m venv .venv
    )
    if errorlevel 1 (
        echo ERROR: Could not create the virtual environment.
        pause
        exit /b 1
    )
)

echo.
echo Installing or verifying required Python packages...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Dependency installation failed. An internet connection may be needed the first time.
    pause
    exit /b 1
)

echo.
echo BioTwin should be available at http://localhost:8000
 echo Keep this window open while using BioTwin.
echo.
".venv\Scripts\python.exe" serve.py
if errorlevel 1 (
    echo.
    echo The server stopped with an error. Copy the message above for troubleshooting.
    pause
)
endlocal
