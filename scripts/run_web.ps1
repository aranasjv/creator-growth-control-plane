$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $root

if (-not (Test-Path '.\apps\web\.env.local')) {
  & powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\configure_desktop.ps1
}

Set-Location .\apps\web
..\..\node_modules\.bin\next.cmd dev --hostname 127.0.0.1 --port 3000
