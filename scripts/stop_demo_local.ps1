$ErrorActionPreference = "SilentlyContinue"

$ports = 8000, 8501
foreach ($port in $ports) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen
    foreach ($conn in $conns) {
        Stop-Process -Id $conn.OwningProcess -Force
    }
}

Write-Host "CivicFlow API and dashboard stopped."
