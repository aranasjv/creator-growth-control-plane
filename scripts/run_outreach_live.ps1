param(
  [string]$Niches = 'pet shops',
  [int]$TimeoutSeconds = 180,
  [int]$Depth = 1,
  [int]$Concurrency = 1,
  [string]$ExitOnInactivity = '90s',
  [int]$MaxEmails = 3,
  [int]$MaxWaitSeconds = 1200
)

$ErrorActionPreference = 'Stop'

$root = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $root

$worker = $null
$startedWorker = $false
$jobId = $null
$jobTimedOut = $false

$existingWorker = Get-CimInstance Win32_Process | Where-Object {
  $_.Name -eq 'python.exe' -and $_.CommandLine -match 'workers\\python-worker\\main.py'
} | Select-Object -First 1

$workerCommand = @"
$env:CGCP_API_BASE_URL='http://localhost:5050'
$env:CGCP_REDIS_URL='redis://localhost:6379/0'
$env:CGCP_QUEUE_NAME='cgcp:jobs'
Set-Location '$root'
.\venv\Scripts\python.exe -u workers\python-worker\main.py
"@

if (-not $existingWorker) {
  $worker = Start-Process powershell -WindowStyle Hidden -ArgumentList '-NoProfile', '-Command', $workerCommand -PassThru
  $startedWorker = $true
} else {
  Write-Host "[outreach-live] Reusing existing worker process $($existingWorker.ProcessId)"
}

try {
  if ($startedWorker) {
    Start-Sleep -Seconds 4
  }

  $job = Invoke-RestMethod -Method Post -Uri 'http://localhost:5050/api/jobs' -ContentType 'application/json' -Body (@{
    type = 'outreach_run'
    provider = 'outreach'
    parameters = @{
      source = 'scripts/run_outreach_live.ps1'
      mode = 'live'
      niche = $Niches
      niches = $Niches
      timeoutSeconds = "$TimeoutSeconds"
      depth = "$Depth"
      concurrency = "$Concurrency"
      exitOnInactivity = $ExitOnInactivity
      maxEmails = "$MaxEmails"
    }
  } | ConvertTo-Json -Depth 6)

  $jobId = $job.jobId
  Write-Host "[outreach-live] Queued live job $jobId for niches: $Niches (max emails: $MaxEmails)"

  $pollIntervalSeconds = 5
  $maxAttempts = [Math]::Ceiling($MaxWaitSeconds / $pollIntervalSeconds)

  for ($attempt = 0; $attempt -lt $maxAttempts; $attempt++) {
    Start-Sleep -Seconds $pollIntervalSeconds
    $jobState = Invoke-RestMethod -Uri "http://localhost:5050/api/jobs/$jobId"

    if ($jobState.status -in @('succeeded', 'failed', 'cancelled')) {
      Write-Host "[outreach-live] Final status: $($jobState.status)"
      if ($jobState.resultJson) {
        Write-Host "[outreach-live] Result: $($jobState.resultJson)"
      }

      if ($jobState.status -ne 'succeeded') {
        throw "Live outreach failed: $($jobState.errorMessage)"
      }

      return
    }
  }

  $jobTimedOut = $true
  throw 'Timed out waiting for live outreach completion.'
}
finally {
  if ($startedWorker) {
    if ($jobTimedOut -and $jobId) {
      powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\cleanup_worker_processes.ps1 -StaleJobId $jobId | Out-Host
    } else {
      powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\cleanup_worker_processes.ps1 | Out-Host
    }
  } elseif ($worker -and -not $worker.HasExited) {
    Stop-Process -Id $worker.Id -Force
  }
}

