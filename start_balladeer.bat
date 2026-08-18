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

REM 4. Auto-Install & Setup ComfyUI for MiniMax Music 3 Neural Synthesis
if not exist "ComfyUI\main.py" (
    echo [*] ComfyUI not detected locally. Setting up ComfyUI for MiniMax Music 3 neural synthesis...
    where git >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        echo [*] Cloning ComfyUI repository...
        git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git ComfyUI
    ) else (
        echo [WARNING] Git is not found in PATH. Skipping ComfyUI automatic clone.
    )
)

if exist "ComfyUI\requirements.txt" (
    if not exist "ComfyUI\.installed" (
        echo [*] Installing ComfyUI core dependencies...
        pip install -r ComfyUI\requirements.txt
        type nul > "ComfyUI\.installed"
    )
)

REM 5. Start ComfyUI Headless Engine in Background if not already running on port 8188
netstat -ano | findstr :8188 >nul 2>nul
if %ERRORLEVEL% neq 0 (
    if exist "ComfyUI\main.py" (
        echo [*] Starting ComfyUI Headless Engine on http://127.0.0.1:8188 ...
        start "Balladeer-ComfyUI-Worker" /min python ComfyUI\main.py --listen 127.0.0.1 --port 8188 --novram
    )
) else (
    echo [*] ComfyUI instance already running on http://127.0.0.1:8188.
)

REM 6. Launch web browser in background after 2 seconds
start "" powershell -NoProfile -Command "Start-Sleep -Seconds 2; Start-Process 'http://localhost:8000'"

echo.
echo ===============================================================================
echo [*] Starting Balladeer Server on http://localhost:8000 ...
echo [*] Server logs and GPU memory stats will stream below.
echo [*] Keep this window OPEN while using Balladeer.
echo [*] Press Ctrl+C in this window to stop the server anytime.
echo ===============================================================================
echo.

REM 7. Launch FastAPI backend in the foreground
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

REM 8. Gracefully terminate background ComfyUI worker on exit
taskkill /FI "WINDOWTITLE eq Balladeer-ComfyUI-Worker*" /F >nul 2>nul

echo.
echo ===============================================================================
echo [*] Balladeer server stopped.
echo ===============================================================================
pause
