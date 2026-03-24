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
$runDir = Join-Path $repoRoot ".run"
New-Item -ItemType Directory -Force $runDir | Out-Null

if (-not (Test-Path $pythonExe)) {
    throw "Missing virtual environment interpreter at $pythonExe"
}

Stop-PortListeners -Ports @($ApiPort, $DashboardPort)

$apiOut = Join-Path $runDir "api.out.log"
$apiErr = Join-Path $runDir "api.err.log"
$dashOut = Join-Path $runDir "dashboard.out.log"
$dashErr = Join-Path $runDir "dashboard.err.log"

Remove-Item $apiOut, $apiErr, $dashOut, $dashErr -Force -ErrorAction SilentlyContinue

$apiProcess = Start-Process `
    -FilePath $pythonExe `
    -WorkingDirectory $repoRoot `
    -ArgumentList @("-m", "uvicorn", "apps.api.main:app", "--host", $HostAddress, "--port", "$ApiPort") `
    -RedirectStandardOutput $apiOut `
    -RedirectStandardError $apiErr `
    -PassThru

$dashboardProcess = Start-Process `
    -FilePath $pythonExe `
    -WorkingDirectory $repoRoot `
    -ArgumentList @("-m", "streamlit", "run", "apps\dashboard\app.py", "--server.headless", "true", "--browser.gatherUsageStats", "false") `
    -RedirectStandardOutput $dashOut `
    -RedirectStandardError $dashErr `
    -PassThru

$apiReady = Wait-HttpReady -Url "http://$HostAddress`:$ApiPort/health" -TimeoutSeconds $TimeoutSeconds
$dashboardReady = Wait-HttpReady -Url "http://$HostAddress`:$DashboardPort" -TimeoutSeconds $TimeoutSeconds

if (-not $apiReady -or -not $dashboardReady) {
    Write-Host ""
    Write-Host "Startup failed." -ForegroundColor Red
    Write-Host "API ready: $apiReady"
    Write-Host "Dashboard ready: $dashboardReady"
    Write-Host ""
    Write-Host "API stderr tail:"
    if (Test-Path $apiErr) { Get-Content $apiErr -Tail 20 }
    Write-Host ""
    Write-Host "Dashboard stderr tail:"
    if (Test-Path $dashErr) { Get-Content $dashErr -Tail 20 }
    exit 1
}

Write-Host ""
Write-Host "CivicFlow started successfully." -ForegroundColor Green
Write-Host "API:       http://$HostAddress`:$ApiPort/health"
Write-Host "Dashboard: http://$HostAddress`:$DashboardPort"
Write-Host "Logs:      $runDir"
Write-Host "API PID:   $($apiProcess.Id)"
Write-Host "UI PID:    $($dashboardProcess.Id)"
