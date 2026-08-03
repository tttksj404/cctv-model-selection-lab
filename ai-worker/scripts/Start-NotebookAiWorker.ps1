[CmdletBinding()]
param(
    [switch]$Once,
    [ValidateSet("DEBUG", "INFO", "WARNING", "ERROR")]
    [string]$LogLevel = "INFO"
)

$ErrorActionPreference = "Stop"
$workerRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $workerRoot

if (-not (Test-Path -LiteralPath ".env" -PathType Leaf)) {
    throw "ai-worker/.env is missing. Copy .env.example and set the central API key and local model paths."
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv was not found on PATH. Install uv before starting the notebook worker."
}

$arguments = @("run", "eyesonu-ai-worker", "--log-level", $LogLevel)
if ($Once) {
    $arguments += "--once"
}

& uv @arguments
exit $LASTEXITCODE
