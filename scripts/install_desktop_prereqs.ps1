$ErrorActionPreference = 'Stop'

function Install-WingetPackage {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Id,
    [Parameter(Mandatory = $true)]
    [string]$Label
  )

  Write-Host "[install] Ensuring $Label is installed..."
  winget install --id $Id --exact --silent --accept-source-agreements --accept-package-agreements
}

function Test-CommandOrPath {
  param(
    [string]$CommandName,
    [string[]]$Paths = @()
  )

  if ($CommandName) {
    $command = Get-Command $CommandName -ErrorAction SilentlyContinue
    if ($command) {
      return $true
    }
  }

  foreach ($path in $Paths) {
    if ($path -and (Test-Path $path)) {
      return $true
    }
  }

  return $false
}

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
  throw 'winget is required to install desktop prerequisites on this machine.'
}

$pythonInstalled = Test-CommandOrPath -CommandName 'py' -Paths @(
  (Join-Path $env:LocalAppData 'Programs\Python\Python312\python.exe'),
  'C:\Users\Jv\AppData\Local\Programs\Python\Python312\python.exe'
)
if (-not $pythonInstalled) {
  Install-WingetPackage -Id 'Python.Python.3.12' -Label 'Python 3.12'
}

if (-not (Test-CommandOrPath -CommandName 'node')) {
  Install-WingetPackage -Id 'OpenJS.NodeJS.LTS' -Label 'Node.js LTS'
}

if (-not (Test-CommandOrPath -CommandName 'dotnet')) {
  Install-WingetPackage -Id 'Microsoft.DotNet.SDK.10' -Label '.NET SDK 10'
}

if (-not (Test-CommandOrPath -CommandName 'docker' -Paths @('C:\Program Files\Docker\Docker\resources\bin\docker.exe'))) {
  Install-WingetPackage -Id 'Docker.DockerDesktop' -Label 'Docker Desktop'
}

if (-not (Test-CommandOrPath -CommandName 'firefox' -Paths @('C:\Program Files\Mozilla Firefox\firefox.exe'))) {
  Install-WingetPackage -Id 'Mozilla.Firefox' -Label 'Mozilla Firefox'
}

if (-not (Test-CommandOrPath -CommandName 'ollama' -Paths @(
  (Join-Path $env:LocalAppData 'Programs\Ollama\ollama.exe'),
  'C:\Program Files\Ollama\ollama.exe'
))) {
  Install-WingetPackage -Id 'Ollama.Ollama' -Label 'Ollama'
}

if (-not (Test-CommandOrPath -CommandName 'magick' -Paths @(Get-ChildItem 'C:\Program Files' -Directory -Filter 'ImageMagick-*' -ErrorAction SilentlyContinue | ForEach-Object { Join-Path $_.FullName 'magick.exe' }))) {
  Install-WingetPackage -Id 'ImageMagick.ImageMagick' -Label 'ImageMagick'
}

if (-not (Test-CommandOrPath -CommandName 'go')) {
  Install-WingetPackage -Id 'GoLang.Go' -Label 'Go'
}

Write-Host '[install] Desktop prerequisites have been handled.'
Write-Host '[install] If Firefox is newly installed, open it once and sign into the accounts you want the automations to use.'
