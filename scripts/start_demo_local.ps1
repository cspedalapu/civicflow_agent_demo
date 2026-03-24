param(
    [string]$HostAddress = "127.0.0.1",
    [int]$ApiPort = 8000,
    [int]$DashboardPort = 8501,
    [int]$TimeoutSeconds = 45
)

$ErrorActionPreference = "Stop"

function Stop-PortListeners {
    param([int[]]$Ports)

    foreach ($port in $Ports) {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        foreach ($conn in $conns) {
            try {
                Stop-Process -Id $conn.OwningProcess -Force -ErrorAction Stop
            } catch {
            }
        }
    }
}

function Wait-HttpReady {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 4
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) {
                return $true
            }
        } catch {
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    throw "Missing virtual environment interpreter at $pythonExe"
}

Stop-PortListeners -Ports @($ApiPort, $DashboardPort)

$apiProcess = Start-Process `
    -FilePath $pythonExe `
    -WorkingDirectory $repoRoot `
    -ArgumentList @("-m", "uvicorn", "apps.api.main:app", "--host", $HostAddress, "--port", "$ApiPort") `
    -PassThru

$dashboardProcess = Start-Process `
    -FilePath $pythonExe `
    -WorkingDirectory $repoRoot `
    -ArgumentList @("-m", "streamlit", "run", "apps\dashboard\app.py", "--server.headless", "true", "--browser.gatherUsageStats", "false") `
    -PassThru

$apiReady = Wait-HttpReady -Url "http://$HostAddress`:$ApiPort/health" -TimeoutSeconds $TimeoutSeconds
$dashboardReady = Wait-HttpReady -Url "http://$HostAddress`:$DashboardPort" -TimeoutSeconds $TimeoutSeconds

if (-not $apiReady -or -not $dashboardReady) {
    $apiExited = $false
    $dashExited = $false
    try { $apiExited = $apiProcess.HasExited } catch {}
    try { $dashExited = $dashboardProcess.HasExited } catch {}

    Write-Host ""
    Write-Host "Startup failed." -ForegroundColor Red
    Write-Host "API ready: $apiReady | PID: $($apiProcess.Id) | Exited: $apiExited"
    Write-Host "Dashboard ready: $dashboardReady | PID: $($dashboardProcess.Id) | Exited: $dashExited"
    exit 1
}

Write-Host ""
Write-Host "CivicFlow started successfully." -ForegroundColor Green
Write-Host "API:       http://$HostAddress`:$ApiPort/health"
Write-Host "Dashboard: http://$HostAddress`:$DashboardPort"
Write-Host "API PID:   $($apiProcess.Id)"
Write-Host "UI PID:    $($dashboardProcess.Id)"
