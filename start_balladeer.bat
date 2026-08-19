@echo off
setlocal enabledelayedexpansion
title Balladeer - Local AI Beat-Synced Video Montage Engine
color 0B
cd /d "%~dp0"

echo ===============================================================================
echo                Balladeer - Local AI Video Montage Engine                       
echo                      (RTX 3070 8GB + 16GB RAM Ready)                          
echo ===============================================================================
echo.

REM 1. Check Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not found in PATH!
    echo Please install Python 3.11+ and ensure 'Add Python to PATH' is checked during installation.
    echo.
    pause
    exit /b 1
)

REM 2. Activate Virtual Environment if present
if exist "venv\Scripts\activate.bat" (
    echo [*] Activating virtual environment: venv
    call venv\Scripts\activate.bat
) else (
    if exist ".venv\Scripts\activate.bat" (
        echo [*] Activating virtual environment: .venv
        call .venv\Scripts\activate.bat
    )
)

REM 3. Build frontend (fast incremental build <1s)
where npm >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [*] Checking and building latest React frontend...
    pushd web
    if not exist "node_modules" call npm install
    call npm run build
    popd
) else (
    if not exist "web\dist\index.html" (
        echo [WARNING] npm was not found and web\dist does not exist.
    )
)

REM 4. Launch web browser in background after 2 seconds
start "" powershell -NoProfile -Command "Start-Sleep -Seconds 2; Start-Process 'http://localhost:8000'"

echo.
echo ===============================================================================
echo [*] Starting Balladeer Server on http://localhost:8000 ...
echo [*] Server logs and GPU memory stats will stream below.
echo [*] Keep this window OPEN while using Balladeer.
echo [*] Press Ctrl+C in this window to stop the server anytime.
echo ===============================================================================
echo.

REM 5. Launch FastAPI backend in the foreground
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

echo.
echo ===============================================================================
echo [*] Balladeer server stopped.
echo ===============================================================================
pause
