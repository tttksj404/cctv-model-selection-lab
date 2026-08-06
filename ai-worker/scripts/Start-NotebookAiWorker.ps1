[CmdletBinding()]
param(
    [switch]$Once,
    [switch]$ValidateOnly,
    [switch]$ProbeRabbit,
    [switch]$NoStatusWindow,
    [ValidateSet("DEBUG", "INFO", "WARNING", "ERROR")]
    [string]$LogLevel = "INFO",
    [string]$EnvFile,
    [ValidateSet("auto", "worker", "device")]
    [string]$AuthMode = "worker",
    [string]$RabbitUsername = "ai-worker-dev",
    [string]$RabbitVhost = "/eyesonu-dev"
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
$env:EYESONU_AI_WORKER_ENV_FILE = $resolvedEnvFile

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv was not found on PATH. Install uv before starting the notebook worker."
}

function Get-DotEnvValues {
    param([string]$Path)

    $values = @{}
    foreach ($rawLine in [System.IO.File]::ReadAllLines($Path)) {
        $line = $rawLine.Trim()
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) {
            continue
        }
        $separator = $line.IndexOf("=")
        if ($separator -lt 1) {
            continue
        }
        $name = $line.Substring(0, $separator).Trim()
        if ($name -notmatch "^[A-Za-z_][A-Za-z0-9_.-]*$") {
            continue
        }
        $values[$name] = $line.Substring($separator + 1).Trim()
    }
    return $values
}

function Set-CompatibilityEnvironment {
    param(
        [hashtable]$Values,
        [string]$SelectedAuthMode,
        [string]$SelectedRabbitUsername,
        [string]$SelectedRabbitVhost
    )

    # The primary contract is RecordingAnalysisWorkerController:
    # /api/v1/internal/recording-analysis-jobs/** with X-Worker-Key.
    # Device API support is opt-in only; never let a media-server Device Key
    # silently select the wrong transport for the internal Worker controller.
    $workerKey = $null
    $candidateNames = if ($SelectedAuthMode -eq "device") {
        @("CENTRAL_API_WORKER_KEY", "AI_WORKER_DEVICE_KEY", "EYESONU_AI_DEVICE_KEY", "EYESONU_AI_WORKER_API_KEY")
    }
    else {
        @("X-Worker-Key", "EYESONU_AI_WORKER_API_KEY", "AI_WORKER_API_KEY", "CENTRAL_API_WORKER_KEY")
    }
    foreach ($candidateName in $candidateNames) {
        if (-not [string]::IsNullOrWhiteSpace($Values[$candidateName])) {
            $workerKey = $Values[$candidateName]
            break
        }
    }
    if ($null -eq $workerKey) {
        throw "AI Worker API key is missing. Set X-Worker-Key for RecordingAnalysisWorkerController in $resolvedEnvFile."
    }
    $normalizedWorkerKey = $workerKey.Trim().Trim('"').Trim("'")
    if ($SelectedAuthMode -eq "device") {
        if ($normalizedWorkerKey -notmatch '^msk_[0-9a-f]{16}\.[0-9a-f]{64}$') {
            throw "CENTRAL_API_WORKER_KEY must be the AI Worker Device Key format msk_<16hex>.<64hex>."
        }
    }
    elseif ($normalizedWorkerKey -match '^msk_[0-9a-f]{16}\.[0-9a-f]{64}$') {
        throw "RecordingAnalysisWorkerController requires a Worker Key in X-Worker-Key; a Device Key cannot be used for this transport."
    }
    $env:EYESONU_AI_WORKER_API_KEY = $normalizedWorkerKey
    $env:EYESONU_AI_WORKER_AUTH_MODE = $SelectedAuthMode

    # The shared local secret table stores the worker password under its account
    # name and keeps rabbitmq_url as an endpoint/template.  Compose the actual
    # AMQP URL only in this child process; no derived credential is written to disk.
    if (
        -not [string]::IsNullOrWhiteSpace($env:EYESONU_AI_WORKER_RABBITMQ_URL) -or
        [string]::IsNullOrWhiteSpace($Values["rabbitmq_url"]) -or
        [string]::IsNullOrWhiteSpace($Values[$SelectedRabbitUsername])
    ) {
        return
    }

    try {
        $endpoint = [System.Uri]$Values["rabbitmq_url"]
    }
    catch {
        throw "rabbitmq_url in $resolvedEnvFile is not a valid AMQP endpoint."
    }
    if ($endpoint.Scheme -notin @("amqp", "amqps") -or [string]::IsNullOrWhiteSpace($endpoint.Host)) {
        throw "rabbitmq_url in $resolvedEnvFile must use amqp or amqps with a host."
    }

    $hostPort = if ($endpoint.IsDefaultPort) {
        $endpoint.Host
    }
    else {
        "{0}:{1}" -f $endpoint.Host, $endpoint.Port
    }
    $encodedUsername = [System.Uri]::EscapeDataString($SelectedRabbitUsername)
    $encodedPassword = [System.Uri]::EscapeDataString($Values[$SelectedRabbitUsername])
    $encodedVhost = [System.Uri]::EscapeDataString($SelectedRabbitVhost)
    $env:EYESONU_AI_WORKER_RABBITMQ_URL = (
        "{0}://{1}:{2}@{3}/{4}" -f $endpoint.Scheme, $encodedUsername, $encodedPassword, $hostPort, $encodedVhost
    )
}

$dotenvValues = Get-DotEnvValues -Path $resolvedEnvFile
$compatibilityParameters = @{
    Values                 = $dotenvValues
    SelectedAuthMode       = $AuthMode
    SelectedRabbitUsername = $RabbitUsername
    SelectedRabbitVhost    = $RabbitVhost
}
Set-CompatibilityEnvironment @compatibilityParameters

if ($ProbeRabbit -and -not $ValidateOnly) {
    throw "-ProbeRabbit is available only with -ValidateOnly so it cannot consume a recording job."
}

if ($ValidateOnly) {
    $env:EYESONU_AI_WORKER_VALIDATE_RABBIT = if ($ProbeRabbit) { "true" } else { "false" }
    $validationCode = @'
import anyio
import os
from pathlib import Path
import aio_pika
from qwen_backend.central_client import CentralWorkerClient
from qwen_backend.solider_clip_engine import validate_realtime_dependencies
from qwen_backend.worker_cli import load_worker_env_file
from qwen_backend.worker_settings import NotebookWorkerSettings

load_worker_env_file(Path(os.environ["EYESONU_AI_WORKER_ENV_FILE"]))
settings = NotebookWorkerSettings()

async def validate() -> int:
    client = CentralWorkerClient(
        base_url=settings.central_api_url,
        api_key=settings.api_key.get_secret_value(),
        worker_id="config-validation",
        auth_mode=settings.auth_mode,
    )
    try:
        if settings.rabbitmq_url is None:
            raise RuntimeError("RabbitMQ URL was not configured")
        validate_realtime_dependencies(
            ffmpeg_path=settings.ffmpeg_path
            if settings.download_window_mode == "segment"
            else None
        )
        rabbit_probe = os.environ.get("EYESONU_AI_WORKER_VALIDATE_RABBIT") == "true"
        if rabbit_probe:
            connection = await aio_pika.connect(settings.rabbitmq_url.get_secret_value(), timeout=15)
            try:
                channel = await connection.channel()
                await channel.close()
            finally:
                await connection.close()
        transport = "device" if client.uses_device_key else "worker"
        print(
            "AI Worker configuration valid: "
            f"transport={transport} rabbitmq_configured=true "
            f"realtime_dependencies=pass download_window={settings.download_window_mode} "
            f"rabbitmq_probe={'pass' if rabbit_probe else 'skipped'}"
        )
        return 0
    finally:
        await client.aclose()

try:
    raise SystemExit(anyio.run(validate))
except (OSError, RuntimeError, ValueError, aio_pika.exceptions.AMQPException) as exception:
    print(f"AI Worker configuration invalid: {exception}")
    raise SystemExit(2)
'@
    $validationCode | & uv run python -
    exit $LASTEXITCODE
}

$arguments = @("run", "eyesonu-ai-worker", "--env-file", $resolvedEnvFile, "--log-level", $LogLevel)
if ($Once) {
    $arguments += "--once"
}
if ($NoStatusWindow) {
    $arguments += "--no-status-window"
}

& uv @arguments
exit $LASTEXITCODE
