# =====================================================================
# start_windows_ui.ps1
# Launch the Windows GUI (PySide6).
#
# Usage (from anywhere):
#     powershell -ExecutionPolicy Bypass -File scripts\start_windows_ui.ps1
#
# Optional environment overrides (one-off):
#     $env:MQTT_BROKER = "192.168.50.1"
#     $env:RTSP_URL    = "rtsp://192.168.50.1:8554/jetson"
#     powershell -ExecutionPolicy Bypass -File scripts\start_windows_ui.ps1
# =====================================================================

$ErrorActionPreference = "Stop"

# Resolve repo root (this script is in <repo>/scripts/)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Resolve-Path (Join-Path $ScriptDir "..")
$AppDir    = Join-Path $RepoRoot "windows_app"
$VenvDir   = Join-Path $RepoRoot ".venv"

Write-Host "==> Repo root: $RepoRoot" -ForegroundColor Cyan

# ----- 1. Activate or hint at venv ----------------------------------
if (Test-Path (Join-Path $VenvDir "Scripts\Activate.ps1")) {
    Write-Host "==> Activating venv: $VenvDir" -ForegroundColor Cyan
    & (Join-Path $VenvDir "Scripts\Activate.ps1")
} else {
    Write-Host "==> No venv at $VenvDir" -ForegroundColor Yellow
    Write-Host "    Create one with:" -ForegroundColor Yellow
    Write-Host "        python -m venv .venv" -ForegroundColor Yellow
    Write-Host "        .\.venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host "        pip install -r windows_app\requirements.txt" -ForegroundColor Yellow
    Write-Host "    Continuing with system Python..." -ForegroundColor Yellow
}

# ----- 2. Sanity-check Python and PySide6 ---------------------------
try {
    $pyver = & python --version 2>&1
    Write-Host "==> $pyver" -ForegroundColor Cyan
} catch {
    Write-Host "Python not found on PATH." -ForegroundColor Red
    exit 1
}

try {
    & python -c "import PySide6, paho.mqtt.client, cv2, numpy" 2>$null
    if ($LASTEXITCODE -ne 0) { throw "import failed" }
} catch {
    Write-Host "==> Required packages missing. Install with:" -ForegroundColor Red
    Write-Host "    pip install -r windows_app\requirements.txt" -ForegroundColor Red
    exit 1
}

# ----- 3. Quick reachability check (non-fatal) ----------------------
$JetsonIP = "192.168.50.1"
Write-Host "==> Pinging Jetson at $JetsonIP ..." -ForegroundColor Cyan
$reachable = Test-Connection -ComputerName $JetsonIP -Count 1 -Quiet -ErrorAction SilentlyContinue
if ($reachable) {
    Write-Host "    OK" -ForegroundColor Green
} else {
    Write-Host "    Not reachable. The GUI will still launch, but RTSP/MQTT may fail." -ForegroundColor Yellow
    Write-Host "    Run scripts\check_network.sh from WSL/Git-Bash for diagnostics." -ForegroundColor Yellow
}

# ----- 4. Launch the app --------------------------------------------
Write-Host "==> Launching GUI..." -ForegroundColor Cyan
Set-Location $AppDir
& python run_app.py
