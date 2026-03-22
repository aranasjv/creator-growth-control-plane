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

$desktopExe = 'C:\Program Files\Docker\Docker\Docker Desktop.exe'
$dockerBin = Split-Path $dockerExe -Parent
$env:PATH = "$dockerBin;$env:PATH"

try {
  & $dockerExe info | Out-Null
} catch {
  if (Test-Path $desktopExe) {
    Write-Host '[stack] Docker Desktop is not ready yet. Starting it now...'
    Start-Process -FilePath $desktopExe | Out-Null
    $ready = $false

    for ($attempt = 0; $attempt -lt 60; $attempt++) {
      Start-Sleep -Seconds 2
      try {
        & $dockerExe info | Out-Null
        $ready = $true
        break
      } catch {
      }
    }

    if (-not $ready) {
      throw 'Docker Desktop did not become ready within 120 seconds.'
    }
  } else {
    throw 'Docker Desktop is installed but the engine is not running.'
  }
}

foreach ($legacyContainer in @('creator-growth-control-plane-postgres', 'creator-growth-control-plane-redis')) {
  $exists = & $dockerExe ps -a --format '{{.Names}}' | Where-Object { $_ -eq $legacyContainer }
  if ($exists) {
    Write-Host "[stack] Removing legacy container $legacyContainer so tech-infra can take over the shared ports..."
    & $dockerExe rm -f $legacyContainer | Out-Null
  }
}

& $dockerExe compose -f infra/docker-compose.yml down --remove-orphans | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw 'Failed to stop the existing tech-infra stack.'
}
foreach ($legacyVolume in @('tech-infra-postgres-data')) {
  $attachedContainers = & $dockerExe ps -a --filter "volume=$legacyVolume" --format '{{.Names}}'
  if (-not $attachedContainers) {
    $volumeExists = & $dockerExe volume ls --format '{{.Name}}' | Where-Object { $_ -eq $legacyVolume }
    if ($volumeExists) {
      Write-Host "[stack] Removing legacy volume $legacyVolume so Postgres 18 can initialize a clean data directory..."
      & $dockerExe volume rm $legacyVolume | Out-Null
      if ($LASTEXITCODE -ne 0) {
        throw "Failed to remove legacy Docker volume $legacyVolume."
      }
    }
  }
}
& $dockerExe compose -f infra/docker-compose.yml pull
if ($LASTEXITCODE -ne 0) {
  throw 'Failed to pull the latest tech-infra images.'
}
& $dockerExe compose -f infra/docker-compose.yml up -d
if ($LASTEXITCODE -ne 0) {
  throw 'Failed to start the tech-infra stack.'
}
Write-Host '[stack] tech-infra Postgres, Redis Stack, and MongoDB are starting.'
