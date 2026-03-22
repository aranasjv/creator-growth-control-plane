$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
Set-Location $root

$env:CGCP_API_BASE_URL = if ($env:CGCP_API_BASE_URL) { $env:CGCP_API_BASE_URL } else { 'http://localhost:5050' }
$env:CGCP_REDIS_URL = if ($env:CGCP_REDIS_URL) { $env:CGCP_REDIS_URL } else { 'redis://localhost:6379/0' }
$env:CGCP_QUEUE_NAME = if ($env:CGCP_QUEUE_NAME) { $env:CGCP_QUEUE_NAME } else { 'cgcp:jobs' }

.\venv\Scripts\python.exe -u workers\python-worker\main.py

