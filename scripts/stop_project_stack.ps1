$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $root

$dockerExe = @(
  (Get-Command docker -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
  'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if (-not $dockerExe) {
  throw 'Docker Desktop is not installed or its CLI could not be located.'
}

$dockerBin = Split-Path $dockerExe -Parent
$env:PATH = "$dockerBin;$env:PATH"

& $dockerExe compose -f .\docker-compose.project.yml down --remove-orphans
if ($LASTEXITCODE -ne 0) {
  throw 'Failed to stop the Creator Growth Control Plane project containers.'
}
Write-Host '[project] Creator Growth Control Plane project containers were stopped.'
