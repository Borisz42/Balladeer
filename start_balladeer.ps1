# Balladeer PowerShell Launcher
$Host.UI.RawUI.WindowTitle = "Balladeer - Local AI Video Montage Engine"
Set-Location -Path $PSScriptRoot

Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "               Balladeer - Local AI Video Montage Engine                       " -ForegroundColor White
Write-Host "                     (RTX 3070 8GB + 16GB RAM Ready)                          " -ForegroundColor Yellow
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
try {
    $pyVersion = & python --version 2>&1
    Write-Host "[*] Detected Python: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python is not found in PATH!" -ForegroundColor Red
    Read-Host "Press Enter to exit..."
    exit 1
}

# Check virtualenv
if (Test-Path "venv\Scripts\Activate.ps1") {
    Write-Host "[*] Activating virtual environment (venv)..." -ForegroundColor Gray
    & "venv\Scripts\Activate.ps1"
} elseif (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "[*] Activating virtual environment (.venv)..." -ForegroundColor Gray
    & ".venv\Scripts\Activate.ps1"
}

# Check and build web/dist
Write-Host "[*] Building latest React frontend..." -ForegroundColor Cyan
Push-Location web
if (-not (Test-Path "node_modules")) {
    & npm install
}
& npm run build
Pop-Location

# Open browser only after backend server is fully ready and responding
Start-Job -ScriptBlock {
    $url = "http://127.0.0.1:8000/api/health"
    $maxAttempts = 120
    for ($i = 0; $i -lt $maxAttempts; $i++) {
        Start-Sleep -Milliseconds 400
        try {
            $resp = Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 1 -ErrorAction Stop
            if ($resp.status -eq "healthy") {
                Start-Process "http://localhost:8000"
                break
            }
        } catch {}
    }
} | Out-Null

Write-Host ""
Write-Host "[*] Starting Uvicorn server on http://localhost:8000 ..." -ForegroundColor Cyan
Write-Host "[*] Logs will stream below. Press Ctrl+C or use Shutdown in UI to stop." -ForegroundColor Gray
Write-Host ""

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Exit 0
