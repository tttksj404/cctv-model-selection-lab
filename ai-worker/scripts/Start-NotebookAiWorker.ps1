[CmdletBinding()]
param(
    [switch]$Once,
    [ValidateSet("DEBUG", "INFO", "WARNING", "ERROR")]
    [string]$LogLevel = "INFO",
    [string]$EnvFile
)

$ErrorActionPreference = "Stop"
$workerRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $workerRoot

if ([string]::IsNullOrWhiteSpace($EnvFile)) {
    $EnvFile = Join-Path $workerRoot ".env"
}

if (-not (Test-Path -LiteralPath $EnvFile -PathType Leaf)) {
    throw "AI Worker environment file is missing: $EnvFile. Copy .env.example or pass -EnvFile <path>."
}

$resolvedEnvFile = (Resolve-Path -LiteralPath $EnvFile -ErrorAction Stop).Path

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv was not found on PATH. Install uv before starting the notebook worker."
}

$arguments = @("run", "eyesonu-ai-worker", "--env-file", $resolvedEnvFile, "--log-level", $LogLevel)
if ($Once) {
    $arguments += "--once"
}

& uv @arguments
exit $LASTEXITCODE
