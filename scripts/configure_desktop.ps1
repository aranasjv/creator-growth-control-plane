$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $root

if (-not (Test-Path 'config.json')) {
  Copy-Item 'config.example.json' 'config.json'
}

$configPath = Join-Path $root 'config.json'
$config = Get-Content $configPath -Raw | ConvertFrom-Json
$configBytes = [System.IO.File]::ReadAllBytes($configPath)
$hasUtf8Bom = $configBytes.Length -ge 3 -and $configBytes[0] -eq 239 -and $configBytes[1] -eq 187 -and $configBytes[2] -eq 191
$updated = $false
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Set-ConfigValueIfMissing {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name,
    [Parameter(Mandatory = $true)]
    [AllowEmptyString()]
    [AllowNull()]
    [string]$Value,
    [string[]]$Placeholders = @()
  )

  if (-not $Value) {
    return
  }

  $currentValue = [string]($config.$Name)
  if ([string]::IsNullOrWhiteSpace($currentValue) -or $Placeholders -contains $currentValue) {
    $config.$Name = $Value
    $script:updated = $true
    Write-Host "[configure] Set $Name to $Value"
  }
}

$imageMagickCandidates = @()
$magickCommand = Get-Command magick -ErrorAction SilentlyContinue
if ($magickCommand) {
  $imageMagickCandidates += $magickCommand.Source
}
$imageMagickCandidates += Get-ChildItem 'C:\Program Files' -Directory -Filter 'ImageMagick-*' -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending |
  ForEach-Object { Join-Path $_.FullName 'magick.exe' }
$imageMagickPath = $imageMagickCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
Set-ConfigValueIfMissing -Name 'imagemagick_path' -Value $imageMagickPath -Placeholders @('Path to magick.exe or on linux/macOS just /usr/bin/convert')
if ($imageMagickPath -and -not (Test-Path ([string]$config.imagemagick_path))) {
  $config.imagemagick_path = $imageMagickPath
  $updated = $true
  Write-Host "[configure] Refreshed imagemagick_path to $imageMagickPath"
}

$profileRoot = Join-Path $env:APPDATA 'Mozilla\Firefox\Profiles'
$profileCandidates = @()
if (Test-Path $profileRoot) {
  $profileCandidates = Get-ChildItem $profileRoot -Directory |
    Sort-Object @{ Expression = { $_.Name -like '*.default-release*' }; Descending = $true }, LastWriteTime -Descending |
    Select-Object -ExpandProperty FullName
}
$firefoxProfile = $profileCandidates | Select-Object -First 1
Set-ConfigValueIfMissing -Name 'firefox_profile' -Value $firefoxProfile
if ($firefoxProfile -and -not (Test-Path ([string]$config.firefox_profile))) {
  $config.firefox_profile = $firefoxProfile
  $updated = $true
  Write-Host "[configure] Refreshed firefox_profile to $firefoxProfile"
}

$ollamaExe = @(
  (Get-Command ollama -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
  (Join-Path $env:LocalAppData 'Programs\Ollama\ollama.exe'),
  'C:\Program Files\Ollama\ollama.exe'
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if ($ollamaExe -and [string]::IsNullOrWhiteSpace([string]$config.ollama_model)) {
  try {
    $models = & $ollamaExe list 2>$null | Select-Object -Skip 1 | ForEach-Object {
      $name = ($_ -split '\s{2,}')[0].Trim()
      if ($name) { $name }
    }
    $defaultModel = $models | Select-Object -First 1
    if ($defaultModel) {
      $config.ollama_model = $defaultModel
      $updated = $true
      Write-Host "[configure] Set ollama_model to $defaultModel"
    }
  } catch {
  }
}

if ($updated -or $hasUtf8Bom) {
  [System.IO.File]::WriteAllText($configPath, ($config | ConvertTo-Json -Depth 10), $utf8NoBom)
  if ($hasUtf8Bom -and -not $updated) {
    Write-Host '[configure] Normalized config.json encoding to UTF-8 without BOM.'
  }
} else {
  Write-Host '[configure] No config.json values needed updating.'
}

$platformEnv = @(
  'NEXT_PUBLIC_API_BASE_URL=http://localhost:5050',
  'API_BASE_URL=http://localhost:5050',
  'CGCP_API_BASE_URL=http://localhost:5050',
  'CGCP_REDIS_URL=redis://localhost:6379/0',
  'CGCP_QUEUE_NAME=cgcp:jobs',
  'MONGO_CONNECTION_STRING=mongodb://mongoadmin:mongopassword@localhost:27017/admin?authSource=admin'
)

[System.IO.File]::WriteAllText((Join-Path $root '.env.platform.local'), (($platformEnv -join [Environment]::NewLine) + [Environment]::NewLine), $utf8NoBom)
[System.IO.File]::WriteAllText((Join-Path $root 'apps\web\.env.local'), ((($platformEnv[0..1]) -join [Environment]::NewLine) + [Environment]::NewLine), $utf8NoBom)

Write-Host '[configure] Wrote .env.platform.local and apps/web/.env.local.'

