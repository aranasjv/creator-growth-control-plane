$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $root

& powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_stack.ps1
& powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\configure_desktop.ps1

$ollamaReachable = $false
try {
  Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/tags -TimeoutSec 2 | Out-Null
  $ollamaReachable = $true
} catch {
}

if (-not $ollamaReachable) {
  $ollamaExe = @(
    (Get-Command ollama -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
    (Join-Path $env:LocalAppData 'Programs\Ollama\ollama.exe'),
    'C:\Program Files\Ollama\ollama.exe'
  ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

  if ($ollamaExe) {
    Start-Process powershell -WorkingDirectory $root -ArgumentList '-NoExit', '-Command', "& '$ollamaExe' serve"
  }
}

Start-Process powershell -WorkingDirectory $root -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-File', 'scripts/run_api.ps1'
Start-Process powershell -WorkingDirectory $root -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-File', 'scripts/run_web.ps1'
Start-Process powershell -WorkingDirectory $root -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-File', 'scripts/run_worker.ps1'

Write-Host '[workspace] Docker services were started and separate windows were opened for API, web, and worker.'
