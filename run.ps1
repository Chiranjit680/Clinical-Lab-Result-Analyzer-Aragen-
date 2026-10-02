<#
    Starts the whole Clinical Lab Result Analyzer stack in one command.

    Usage:  .\run.ps1                 start all three services
            .\run.ps1 -Install        force a dependency reinstall first
            .\run.ps1 -SkipPatient    analyzer + frontend only (no Postgres needed)

    Analyzer Service -> http://127.0.0.1:8000   (FastAPI + MCP server subprocess)
    patientService   -> http://127.0.0.1:8082   (Spring Boot + Postgres)
    Frontend         -> http://localhost:5173   (Vite dev server)

    If any of those ports is taken, the next free one is used and the new value
    is passed to whatever depends on it: the back ends are told which origin to
    allow through CORS, and the frontend is told which URLs to call. Moving a
    port without propagating it would break every request with no visible
    cause, so all three are chosen together before anything starts.

    Press Ctrl+C to stop everything.
#>
param(
    [switch]$Install,
    [switch]$SkipPatient
)

$ErrorActionPreference = "Stop"

$root       = $PSScriptRoot
$analyzer   = Join-Path $root "Analyzer Service\backend"
$patient    = Join-Path $root "patientService\patientService"
$frontend   = Join-Path $root "frontend"
$venvPython = Join-Path $analyzer "venv\Scripts\python.exe"

# Tracks every process we spawn so the finally block can stop all of them.
$script:started = @()

function Stop-All {
    foreach ($entry in $script:started) {
        $proc = $entry.Process
        if ($proc -and -not $proc.HasExited) {
            Write-Host "Stopping $($entry.Name) (PID $($proc.Id))..." -ForegroundColor Yellow
            # /T kills the tree: uvicorn's reloader spawns the MCP server, and
            # Maven spawns the JVM. Killing only the parent orphans those and
            # leaves the ports bound.
            & taskkill /PID $proc.Id /T /F 2>&1 | Out-Null
        }
    }
}

function Test-PortBusy {
    param([int]$Port)
    $busy = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    return $null -ne $busy
}

function Get-FreePort {
    param([int]$Preferred, [string]$Name)

    foreach ($port in $Preferred..($Preferred + 20)) {
        if (-not (Test-PortBusy -Port $port)) {
            if ($port -ne $Preferred) {
                Write-Host "Port $Preferred is busy - $Name will use $port instead." -ForegroundColor Yellow
            }
            return $port
        }
    }
    throw "No free port for $Name between $Preferred and $($Preferred + 20)."
}

function Wait-ForService {
    param([string]$Name, [string]$Url, [int]$Attempts = 40, [System.Diagnostics.Process]$Process)

    foreach ($i in 1..$Attempts) {
        Start-Sleep -Milliseconds 750
        if ($Process -and $Process.HasExited) {
            throw "$Name exited during startup (code $($Process.ExitCode)). Scroll up for its error output."
        }
        try {
            Invoke-WebRequest -Uri $Url -TimeoutSec 3 -UseBasicParsing | Out-Null
            Write-Host "$Name is up." -ForegroundColor Green
            return $true
        }
        catch {
            # A 4xx still means the server is answering, which is all we need.
            if ($_.Exception.Response) {
                Write-Host "$Name is up." -ForegroundColor Green
                return $true
            }
        }
    }
    Write-Host "$Name did not answer in time - continuing anyway." -ForegroundColor Yellow
    return $false
}

function Start-Service-Process {
    param([string]$Name, [string]$FilePath, [string[]]$Arguments, [string]$WorkingDirectory)

    Write-Host "Starting $Name..." -ForegroundColor Green
    $proc = Start-Process -FilePath $FilePath -ArgumentList $Arguments `
        -WorkingDirectory $WorkingDirectory -PassThru -NoNewWindow
    $script:started += [pscustomobject]@{ Name = $Name; Process = $proc }
    return $proc
}

try {
    # ---------- layout checks ----------
    if (-not (Test-Path $analyzer)) { throw "Analyzer backend not found at $analyzer" }
    if (-not (Test-Path $frontend)) { throw "frontend/ not found at $frontend" }
    if (-not $SkipPatient -and -not (Test-Path $patient)) {
        throw "patientService not found at $patient (use -SkipPatient to run without it)"
    }

    # ---------- port allocation ----------
    # Resolved before anything starts, because each service has to be told the
    # ports the others ended up on.
    $analyzerPort = Get-FreePort -Preferred 8000 -Name "Analyzer Service"
    $frontendPort = Get-FreePort -Preferred 5173 -Name "frontend"
    $patientPort = 0
    if (-not $SkipPatient) { $patientPort = Get-FreePort -Preferred 8082 -Name "patientService" }

    $frontendOrigins = "http://localhost:$frontendPort,http://127.0.0.1:$frontendPort"

    if (-not $SkipPatient -and -not (Test-PortBusy -Port 5432)) {
        Write-Host "WARNING: nothing is listening on 5432 - patientService needs Postgres and will fail to start." -ForegroundColor Yellow
    }

    if (-not (Test-Path (Join-Path $analyzer ".env"))) {
        Write-Host "WARNING: Analyzer Service\backend\.env not found - copy .env.example and add your API key." -ForegroundColor Yellow
    }

    # ---------- analyzer dependencies ----------
    if (-not (Test-Path $venvPython)) {
        Write-Host "Creating Python virtual environment..." -ForegroundColor Cyan
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & py -3.12 -m venv (Join-Path $analyzer "venv")
        }
        else {
            & python -m venv (Join-Path $analyzer "venv")
        }
        $Install = $true
    }

    if ($Install) {
        Write-Host "Installing analyzer dependencies..." -ForegroundColor Cyan
        & $venvPython -m pip install --quiet -r (Join-Path $analyzer "requirements.txt")
    }

    # ---------- frontend dependencies ----------
    if ($Install -or -not (Test-Path (Join-Path $frontend "node_modules"))) {
        Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
        Push-Location $frontend
        try { & npm install } finally { Pop-Location }
    }

    # ---------- analyzer ----------
    # Spawned processes inherit these, which is how the chosen ports reach them.
    $env:PORT = "$analyzerPort"
    $env:CORS_ORIGINS = $frontendOrigins
    $analyzerProc = Start-Service-Process -Name "Analyzer Service (:$analyzerPort)" `
        -FilePath $venvPython -Arguments @("-m", "app.main") -WorkingDirectory $analyzer
    # The MCP server is spawned as a subprocess during startup, so this takes
    # a few seconds longer than a plain FastAPI boot.
    Wait-ForService -Name "Analyzer Service" -Url "http://127.0.0.1:$analyzerPort/health" -Process $analyzerProc | Out-Null

    # ---------- patient service ----------
    if (-not $SkipPatient) {
        $mvnw = Join-Path $patient "mvnw.cmd"
        if (-not (Test-Path $mvnw)) { $mvnw = Join-Path $patient "mvnw" }

        $env:SERVER_PORT = "$patientPort"
        $env:APP_CORS_ORIGINS = $frontendOrigins
        $patientProc = Start-Service-Process -Name "patientService (:$patientPort)" `
            -FilePath $mvnw -Arguments @("spring-boot:run") -WorkingDirectory $patient
        # First run downloads Maven dependencies and runs Flyway, so allow longer.
        Wait-ForService -Name "patientService" -Url "http://127.0.0.1:$patientPort/api/identities" `
            -Attempts 120 -Process $patientProc | Out-Null
    }

    # ---------- frontend (foreground, so Ctrl+C lands here) ----------
    # Vite exposes VITE_* variables to the app, which is how api.js and
    # patientApi.js learn where the back ends ended up.
    $env:VITE_API_BASE = "http://127.0.0.1:$analyzerPort"
    if (-not $SkipPatient) { $env:VITE_PATIENT_API_BASE = "http://127.0.0.1:$patientPort" }
    # Vite honours PORT in some setups; clear it so -port is unambiguous.
    Remove-Item Env:PORT -ErrorAction SilentlyContinue

    Write-Host ""
    Write-Host "  Analyzer Service  http://127.0.0.1:$analyzerPort" -ForegroundColor Cyan
    if (-not $SkipPatient) {
        Write-Host "  patientService    http://127.0.0.1:$patientPort" -ForegroundColor Cyan
    }
    Write-Host "  Frontend          http://localhost:$frontendPort" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Press Ctrl+C to stop all services." -ForegroundColor Cyan
    Write-Host ""

    Push-Location $frontend
    # --strictPort makes Vite fail loudly rather than drifting to a port the
    # back ends were never told to allow.
    try { & npm run dev -- --port $frontendPort --strictPort } finally { Pop-Location }
}
finally {
    Write-Host ""
    Stop-All
}
