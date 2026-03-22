$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $root
$env:DOTNET_CLI_HOME = Join-Path $root '.dotnet-home'
$env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = '1'
$env:DOTNET_NOLOGO = '1'
New-Item -ItemType Directory -Force -Path $env:DOTNET_CLI_HOME | Out-Null

dotnet run --project .\apps\api\CreatorGrowthControlPlane.Orchestrator.csproj --urls http://localhost:5050

