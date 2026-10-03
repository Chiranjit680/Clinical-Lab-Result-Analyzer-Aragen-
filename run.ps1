<#
    Starts the whole Clinical Lab Result Analyzer stack in one command.

    Usage:  .\run.ps1                 start everything
            .\run.ps1 -Install        force a dependency reinstall first
            .\run.ps1 -SkipPatient    skip patientService (no Postgres needed)
            .\run.ps1 -SkipEmail      skip the email service
            .\run.ps1 -SkipVlm        skip the VLM agent service

    Analyzer Service -> http://127.0.0.1:8000   (FastAPI + MCP server subprocess)
    patientService   -> http://127.0.0.1:8082   (Spring Boot + Postgres)
    email_service    -> http://127.0.0.1:8083   (FastAPI + Gmail API)
    vlm_agents       -> http://127.0.0.1:8084   (FastAPI + LangGraph image agents)
    Frontend         -> http://localhost:5173   (Vite dev server)

    If a port is taken the next free one is used, and the new value is passed to
    everything that depends on it: the back ends are told which origin to allow
    through CORS, patientService is told where the analyzer and email services
    ended up, and the frontend is told which URLs to call. Moving a port without
    propagating it breaks requests with no visible cause, so every port is
    chosen before anything starts.

    Press Ctrl+C to stop everything.
#>
param(
    [switch]$Install,
    [switch]$SkipPatient,
    [switch]$SkipEmail,
    [switch]$SkipVlm
)

$ErrorActionPreference = "Stop"

$root     = $PSScriptRoot
$analyzer = Join-Path $root "Analyzer Service\backend"
$patient  = Join-Path $root "patientService\patientService"
$email    = Join-Path $root "email_service"
$vlm      = Join-Path $root "vlm_agents"
$frontend = Join-Path $root "frontend"

$analyzerPython = Join-Path $analyzer "venv\Scripts\python.exe"
$emailPython    = Join-Path $email "venv\Scripts\python.exe"
$vlmPython      = Join-Path $vlm "venv\Scripts\python.exe"

# Tracks every process we spawn so the finally block can stop all of them.
$script:started = @()

function Stop-All {
    foreach ($entry in $script:started) {
        $proc = $entry.Process
        if ($proc -and -not $proc.HasExited) {
            Write-Host "Stopping $($entry.Name) (PID $($proc.Id))..." -ForegroundColor Yellow
            # /T kills the tree: uvicorn spawns the MCP server, and Maven spawns
            # the JVM. Killing only the parent orphans those and leaves the
            # ports bound.
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

function Ensure-Venv {
    param([string]$Dir, [string]$PythonPath, [string]$Name)

    if (Test-Path $PythonPath) { return $false }
    Write-Host "Creating the $Name virtual environment..." -ForegroundColor Cyan
    # Out-Null on both: anything these print would otherwise be returned
    # alongside the boolean, and the caller's `if` would always see a truthy
    # array.
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 -m venv (Join-Path $Dir "venv") | Out-Null
    }
    else {
        & python -m venv (Join-Path $Dir "venv") | Out-Null
    }
    return $true   # caller should install into the new venv
}

function Install-Requirements {
    param([string]$PythonPath, [string]$Dir, [string]$Name)

    $requirements = Join-Path $Dir "requirements.txt"
    if (-not (Test-Path $requirements)) { return }
    Write-Host "Installing $Name dependencies..." -ForegroundColor Cyan
    & $PythonPath -m pip install --quiet -r $requirements
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
            return
        }
        catch {
            # A 4xx still means the server is answering, which is all we need.
            if ($_.Exception.Response) {
                Write-Host "$Name is up." -ForegroundColor Green
                return
            }
        }
    }
    Write-Host "$Name did not answer in time - continuing anyway." -ForegroundColor Yellow
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
    if (-not $SkipEmail -and -not (Test-Path $email)) {
        Write-Host "email_service not found - skipping it." -ForegroundColor Yellow
        $SkipEmail = $true
    }
    if (-not $SkipVlm -and -not (Test-Path $vlm)) {
        Write-Host "vlm_agents not found - skipping it." -ForegroundColor Yellow
        $SkipVlm = $true
    }

    # ---------- port allocation ----------
    # Every port is resolved before anything starts, because each service has to
    # be told where the others ended up.
    $analyzerPort = Get-FreePort -Preferred 8000 -Name "Analyzer Service"
    $frontendPort = Get-FreePort -Preferred 5173 -Name "frontend"
    $patientPort = 0
    $emailPort = 0
    $vlmPort = 0
    if (-not $SkipPatient) { $patientPort = Get-FreePort -Preferred 8082 -Name "patientService" }
    if (-not $SkipEmail)   { $emailPort   = Get-FreePort -Preferred 8083 -Name "email_service" }
    if (-not $SkipVlm)     { $vlmPort     = Get-FreePort -Preferred 8084 -Name "vlm_agents" }

    $frontendOrigins = "http://localhost:$frontendPort,http://127.0.0.1:$frontendPort"

    # ---------- preflight warnings ----------
    if (-not $SkipPatient -and -not (Test-PortBusy -Port 5432)) {
        Write-Host "WARNING: nothing is listening on 5432 - patientService needs Postgres and will fail to start." -ForegroundColor Yellow
    }
    if (-not (Test-Path (Join-Path $analyzer ".env"))) {
        Write-Host "WARNING: Analyzer Service\backend\.env not found - copy .env.example and add your API key." -ForegroundColor Yellow
    }
    if (-not $SkipEmail -and -not (Test-Path (Join-Path $email "credentials.json"))) {
        Write-Host "WARNING: email_service\credentials.json not found - sending mail will fail with a 503." -ForegroundColor Yellow
    }

    # ---------- dependencies ----------
    if (Ensure-Venv -Dir $analyzer -PythonPath $analyzerPython -Name "analyzer") { $Install = $true }
    if ($Install) { Install-Requirements -PythonPath $analyzerPython -Dir $analyzer -Name "analyzer" }

    if (-not $SkipEmail) {
        if (Ensure-Venv -Dir $email -PythonPath $emailPython -Name "email service") {
            Install-Requirements -PythonPath $emailPython -Dir $email -Name "email service"
        }
        elseif ($Install) {
            Install-Requirements -PythonPath $emailPython -Dir $email -Name "email service"
        }
    }

    if (-not $SkipVlm) {
        if (Ensure-Venv -Dir $vlm -PythonPath $vlmPython -Name "VLM agents") {
            Install-Requirements -PythonPath $vlmPython -Dir $vlm -Name "VLM agents"
        }
        elseif ($Install) {
            Install-Requirements -PythonPath $vlmPython -Dir $vlm -Name "VLM agents"
        }
    }

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
        -FilePath $analyzerPython -Arguments @("-m", "app.main") -WorkingDirectory $analyzer
    # The MCP server is spawned as a subprocess during startup, so this takes a
    # few seconds longer than a plain FastAPI boot.
    Wait-ForService -Name "Analyzer Service" -Url "http://127.0.0.1:$analyzerPort/health" -Process $analyzerProc

    # ---------- email service ----------
    if (-not $SkipEmail) {
        [Environment]::SetEnvironmentVariable("PORT", $null)
        $emailProc = Start-Service-Process -Name "email_service (:$emailPort)" `
            -FilePath $emailPython `
            -Arguments @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "$emailPort") `
            -WorkingDirectory $email
        Wait-ForService -Name "email_service" -Url "http://127.0.0.1:$emailPort/health" -Process $emailProc
    }

    # ---------- VLM agents ----------
    if (-not $SkipVlm) {
        # Nothing is injected here: the service loads vlm_agents\.env itself, so
        # it behaves the same whether it is started by this script or deployed
        # on its own. Injecting would silently win over that file.
        if (-not (Test-Path (Join-Path $vlm ".env"))) {
            Write-Host "WARNING: vlm_agents\.env not found - copy .env.example and add your API key." -ForegroundColor Yellow
        }

        # Started from the repository root, not from vlm_agents: the MCP tool
        # server is spawned as `python -m vlm_agents.mcp_server`, which only
        # resolves if the package's parent is the working directory.
        $vlmProc = Start-Service-Process -Name "vlm_agents (:$vlmPort)" `
            -FilePath $vlmPython `
            -Arguments @("-m", "uvicorn", "vlm_agents.main:app", "--host", "127.0.0.1", "--port", "$vlmPort") `
            -WorkingDirectory $root
        Wait-ForService -Name "vlm_agents" -Url "http://127.0.0.1:$vlmPort/health" -Process $vlmProc
    }

    # ---------- patient service ----------
    if (-not $SkipPatient) {
        $mvnw = Join-Path $patient "mvnw.cmd"
        if (-not (Test-Path $mvnw)) { $mvnw = Join-Path $patient "mvnw" }

        $env:SERVER_PORT = "$patientPort"
        $env:APP_CORS_ORIGINS = $frontendOrigins
        # application.yml hardcodes 8000 and 8083; without these a shifted port
        # would leave patientService calling services that are not there.
        $env:APP_ANALYZER_BASE_URL = "http://127.0.0.1:$analyzerPort"
        if (-not $SkipEmail) {
            $env:APP_EMAIL_SERVICE_BASE_URL = "http://127.0.0.1:$emailPort"
        }

        $patientProc = Start-Service-Process -Name "patientService (:$patientPort)" `
            -FilePath $mvnw -Arguments @("spring-boot:run") -WorkingDirectory $patient
        # First run resolves Maven dependencies and runs Flyway, so allow longer.
        Wait-ForService -Name "patientService" -Url "http://127.0.0.1:$patientPort/api/identities" `
            -Attempts 120 -Process $patientProc
    }

    # ---------- frontend (foreground, so Ctrl+C lands here) ----------
    # Vite exposes VITE_* variables to the app, which is how api.js, patientApi.js
    # and vlmApi.js learn where the back ends ended up.
    $env:VITE_API_BASE = "http://127.0.0.1:$analyzerPort"
    if (-not $SkipPatient) { $env:VITE_PATIENT_API_BASE = "http://127.0.0.1:$patientPort" }
    if (-not $SkipVlm)     { $env:VITE_VLM_API_BASE = "http://127.0.0.1:$vlmPort" }
    # Vite honours PORT in some setups; clear it so -port is unambiguous.
    [Environment]::SetEnvironmentVariable("PORT", $null)

    Write-Host ""
    Write-Host "  Analyzer Service  http://127.0.0.1:$analyzerPort" -ForegroundColor Cyan
    if (-not $SkipPatient) { Write-Host "  patientService    http://127.0.0.1:$patientPort" -ForegroundColor Cyan }
    if (-not $SkipEmail)   { Write-Host "  email_service     http://127.0.0.1:$emailPort" -ForegroundColor Cyan }
    if (-not $SkipVlm)     { Write-Host "  vlm_agents        http://127.0.0.1:$vlmPort" -ForegroundColor Cyan }
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
