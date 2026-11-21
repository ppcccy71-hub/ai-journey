# One-click start: build frontend if needed, then serve API + SPA on one port.
# Usage:
#   .\start.ps1
#   .\start.ps1 -Port 8080
#   .\start.ps1 -NoBrowser

param(
    [int]$Port = 8000,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontend = Join-Path $root "frontend"
$build = Join-Path $root "build"

if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host "[1/3] Installing frontend deps (first run, about 1 min)..." -ForegroundColor Cyan
    Push-Location $frontend
    npm install --no-audit --no-fund
    Pop-Location
}

if (-not (Test-Path (Join-Path $frontend "dist"))) {
    Write-Host "[2/3] Building frontend..." -ForegroundColor Cyan
    Push-Location $frontend
    npm run build
    Pop-Location
}

Write-Host "[3/3] Serving on http://127.0.0.1:$Port" -ForegroundColor Green
Write-Host "      API docs: http://127.0.0.1:$Port/docs    (Ctrl+C to stop)" -ForegroundColor DarkGray

if (-not $NoBrowser) {
    Start-Sleep -Seconds 1
    Start-Process ("http://127.0.0.1:" + $Port)
}

Set-Location $build
python -m uvicorn app:app --host 127.0.0.1 --port $Port
