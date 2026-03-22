$ErrorActionPreference = 'Stop'
$apiBaseUrl = if ($env:CGCP_API_BASE_URL) { $env:CGCP_API_BASE_URL } else { 'http://localhost:5050' }

$job = Invoke-RestMethod -Method Post -Uri "$apiBaseUrl/api/jobs" -ContentType 'application/json' -Body (@{
  type = 'smoke_test'
  provider = 'system'
  parameters = @{
    source = 'scripts/smoke_test_stack.ps1'
  }
} | ConvertTo-Json -Depth 4)

$jobId = $job.jobId
Write-Host "[smoke] Queued smoke_test job $jobId"

for ($attempt = 0; $attempt -lt 30; $attempt++) {
  Start-Sleep -Seconds 2
  $jobState = Invoke-RestMethod -Uri "$apiBaseUrl/api/jobs/$jobId"

  if ($jobState.status -in @('succeeded', 'failed', 'cancelled')) {
    Write-Host "[smoke] Final status: $($jobState.status)"
    if ($jobState.resultJson) {
      Write-Host "[smoke] Result: $($jobState.resultJson)"
    }

    if ($jobState.status -ne 'succeeded') {
      throw "Smoke test failed: $($jobState.errorMessage)"
    }

    return
  }
}

throw 'Smoke test timed out waiting for the worker to complete.'

