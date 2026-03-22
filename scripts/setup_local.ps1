$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $root

$candidates = @(
  (Join-Path $env:LocalAppData 'Programs\Python\Python312\python.exe'),
  'C:\Users\Jv\AppData\Local\Programs\Python\Python312\python.exe'
)

$pythonExe = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if (-not $pythonExe) {
  throw 'Python 3.12 is not installed. Install it first with scripts/install_desktop_prereqs.ps1.'
}

if (-not (Test-Path 'config.json')) {
  Copy-Item 'config.example.json' 'config.json'
  Write-Host '[setup] Created config.json from config.example.json'
}

& $pythonExe -m venv venv
.\venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m pip install -r workers\python-worker\requirements.txt

npm.cmd install

$env:DOTNET_CLI_HOME = Join-Path $root '.dotnet-home'
$env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = '1'
$env:DOTNET_NOLOGO = '1'
New-Item -ItemType Directory -Force -Path $env:DOTNET_CLI_HOME | Out-Null

dotnet restore .\apps\api\CreatorGrowthControlPlane.Orchestrator.csproj
& powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\configure_desktop.ps1

Write-Host '[setup] Complete.'
Write-Host '[setup] Start shared tech-infra with: docker compose -f infra/docker-compose.yml up -d'
Write-Host '[setup] Start API with: npm.cmd run dev:api'
Write-Host '[setup] Start web with: npm.cmd run dev:web'
Write-Host '[setup] Start worker with: npm.cmd run dev:worker'
Write-Host '[setup] Or open separate windows for everything with: npm.cmd run start:desktop'

