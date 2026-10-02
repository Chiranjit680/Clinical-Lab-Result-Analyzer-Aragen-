<#
    Starts the Lab Results Analyzer (backend + frontend) in one command.

    Usage:  .\run.ps1              start both servers
            .\run.ps1 -Install     force a dependency reinstall first

    Backend  -> http://127.0.0.1:8000   (FastAPI + MCP server subprocess)
    Frontend -> http://localhost:5173   (Vite dev server)

    Press Ctrl+C to stop both.
#>
param(
    [switch]$Install
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$repoRoot = Split-Path $root -Parent
$backend = Join-Path $root "backend"
# The frontend is shared by both services, so it lives at the repository root
# rather than inside "Analyzer Service" alongside this script.
$frontend = Join-Path $repoRoot "frontend"
$venvPython = Join-Path $backend "venv\Scripts\python.exe"

$backendProcess = $null

function Stop-Servers {
    if ($script:backendProcess -and -not $script:backendProcess.HasExited) {
        Write-Host "`nStopping backend (PID $($script:backendProcess.Id))..." -ForegroundColor Yellow
        # Kill the whole tree: uvicorn's reloader and the MCP server subprocess
        # are children, and would otherwise keep port 8000 bound.
        & taskkill /PID $script:backendProcess.Id /T /F 2>&1 | Out-Null
    }
}

try {
    # ---------- checks ----------
    if (-not (Test-Path $backend)) { throw "backend/ not found at $backend" }
    if (-not (Test-Path $frontend)) { throw "frontend/ not found at $frontend (expected at the repository root, beside 'Analyzer Service')" }

    if (-not (Test-Path (Join-Path $backend ".env"))) {
        Write-Host "WARNING: backend\.env not found - copy .env.example and add your API key." -ForegroundColor Yellow
    }

    # ---------- backend deps ----------
    if (-not (Test-Path $venvPython)) {
        Write-Host "Creating Python virtual environment..." -ForegroundColor Cyan
        $py = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
        if ($py -eq "py") { & py -3.12 -m venv (Join-Path $backend "venv") }
        else { & python -m venv (Join-Path $backend "venv") }
        $Install = $true
    }

    if ($Install) {
        Write-Host "Installing backend dependencies..." -ForegroundColor Cyan
        & $venvPython -m pip install --quiet -r (Join-Path $backend "requirements.txt")
    }

    # ---------- frontend deps ----------
    if ($Install -or -not (Test-Path (Join-Path $frontend "node_modules"))) {
        Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
        Push-Location $frontend
        try { & npm install } finally { Pop-Location }
    }

    # ---------- start backend ----------
    Write-Host "Starting backend on http://127.0.0.1:8000 ..." -ForegroundColor Green
    $backendProcess = Start-Process -FilePath $venvPython `
        -ArgumentList "-m", "app.main" `
        -WorkingDirectory $backend `
        -PassThru -NoNewWindow
    $script:backendProcess = $backendProcess

    # Wait for the API to answer before starting the UI, so the first request
    # from the browser can't race backend startup (the MCP subprocess spawn
    # makes startup take a few seconds).
    $ready = $false
    foreach ($attempt in 1..30) {
        Start-Sleep -Milliseconds 700
        if ($backendProcess.HasExited) { throw "Backend exited during startup (code $($backendProcess.ExitCode))." }
        try {
            Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2 | Out-Null
            $ready = $true
            break
        } catch { }
    }
    if ($ready) { Write-Host "Backend is up." -ForegroundColor Green }
    else { Write-Host "Backend did not answer /health yet - continuing anyway." -ForegroundColor Yellow }

    # ---------- start frontend (foreground) ----------
    Write-Host "Starting frontend on http://localhost:5173 ..." -ForegroundColor Green
    Write-Host "Note: the 'Add lab report' page also needs patientService on :8082, which this script does not start." -ForegroundColor DarkGray
    Write-Host "Press Ctrl+C to stop both servers.`n" -ForegroundColor Cyan
    Push-Location $frontend
    try { & npm run dev } finally { Pop-Location }
}
finally {
    Stop-Servers
}
