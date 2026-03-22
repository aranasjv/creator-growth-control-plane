param(
  [string]$StaleJobId
)

$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $root

$targets = Get-CimInstance Win32_Process | Where-Object {
  ($_.Name -eq 'python.exe' -and ($_.CommandLine -match 'workers\\python-worker\\main.py' -or $_.CommandLine -match 'src\\worker_task.py')) -or
  ($_.Name -eq 'google-maps-scraper.exe' -and $_.CommandLine -match 'creator-growth-control-plane') -or
  ($_.Name -eq 'powershell.exe' -and $_.CommandLine -match 'creator-growth-control-plane' -and ($_.CommandLine -match 'python-worker\\main.py' -or $_.CommandLine -match 'run_outreach_dry_run.ps1' -or $_.CommandLine -match 'run_worker.ps1'))
}

foreach ($proc in $targets) {
  try {
    Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
    Write-Host "[cleanup] Stopped $($proc.Name) $($proc.ProcessId)"
  } catch {
  }
}

if ($StaleJobId) {
  Invoke-RestMethod -Method Post -Uri "http://localhost:5050/api/internal/jobs/$StaleJobId/status" -ContentType 'application/json' -Body (@{
    status = 'failed'
    errorMessage = 'Stopped stale outreach dry-run worker process during cleanup.'
  } | ConvertTo-Json) | Out-Null
  Write-Host "[cleanup] Marked stale job $StaleJobId as failed."
}
