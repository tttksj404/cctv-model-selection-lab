from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TypeAlias

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    TypeAdapter,
    ValidationError,
)

PathLookup: TypeAlias = Callable[[str], str | None]

DEFAULT_SONNET_MODEL: Final = "sonnet"
_LEGACY_WINDOWS_PATH: Final = (
    Path.home()
    / "AppData/Local/claude-code-cli/node_modules/@anthropic-ai/claude-code/bin/claude.exe"
)
_JSON_OBJECT = TypeAdapter(dict[str, JsonValue])


class SonnetCLIError(RuntimeError):
    pass


class ClaudeExecutableError(SonnetCLIError):
    pass


class ClaudeAuthError(SonnetCLIError):
    pass


class SonnetTeacherError(SonnetCLIError):
    pass


class _AuthEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=True)

    logged_in: bool = Field(alias="loggedIn")
    auth_method: str = Field(alias="authMethod")
    api_provider: str = Field(alias="apiProvider")
    subscription_type: str | None = Field(default=None, alias="subscriptionType")


@dataclass(frozen=True, slots=True)
class ClaudeAuthStatus:
    logged_in: bool
    auth_method: str
    api_provider: str
    subscription_type: str | None


@dataclass(frozen=True, slots=True)
class SonnetCLIConfig:
    executable: Path
    model: str = DEFAULT_SONNET_MODEL
    timeout_seconds: int = 180
    max_turns: int = 2


@dataclass(frozen=True, slots=True)
class SonnetTeacherResult:
    structured_output: dict[str, JsonValue]
    requested_model: str


def resolve_claude_executable(
    explicit: Path | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    path_lookup: PathLookup = shutil.which,
) -> Path:
    """Resolve Claude from an explicit path, project override, PATH, or legacy install."""
    environment = os.environ if environ is None else environ
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit)
    configured = environment.get("CCTV_CLAUDE_BIN", "").strip()
    if configured:
        candidates.append(Path(configured).expanduser())
    discovered = path_lookup("claude")
    if discovered:
        candidates.append(Path(discovered))
    candidates.append(_LEGACY_WINDOWS_PATH)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise ClaudeExecutableError(
        "Claude CLI executable was not found; install `claude` or set CCTV_CLAUDE_BIN"
    )


def parse_auth_status(raw: str) -> ClaudeAuthStatus:
    """Parse the secret-free subset of `claude auth status`."""
    try:
        envelope = _AuthEnvelope.model_validate_json(raw)
    except ValidationError as error:
        raise ClaudeAuthError("Claude auth status returned an invalid response") from error
    if not envelope.logged_in:
        raise ClaudeAuthError("Claude CLI is not logged in")
    return ClaudeAuthStatus(
        logged_in=envelope.logged_in,
        auth_method=envelope.auth_method,
        api_provider=envelope.api_provider,
        subscription_type=envelope.subscription_type,
    )


def inspect_auth_status(config: SonnetCLIConfig) -> ClaudeAuthStatus:
    """Run the CLI authentication preflight without exposing account identifiers."""
    completed = subprocess.run(
        [str(config.executable), "auth", "status"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=min(config.timeout_seconds, 30),
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip()[-300:]
        raise ClaudeAuthError(
            f"Claude auth status failed with return code {completed.returncode}: {detail}"
        )
    return parse_auth_status(completed.stdout)


def build_teacher_command(
    config: SonnetCLIConfig,
    *,
    prompt: str,
    schema: Mapping[str, JsonValue],
) -> list[str]:
    """Build the non-interactive, read-only structured teacher command."""
    if not prompt.strip():
        raise SonnetTeacherError("teacher prompt must not be empty")
    if not config.model.strip():
        raise SonnetTeacherError("teacher model must not be empty")
    if config.max_turns < 1:
        raise SonnetTeacherError("max_turns must be at least one")
    return [
        str(config.executable),
        "-p",
        prompt,
        "--model",
        config.model,
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(dict(schema), ensure_ascii=False, separators=(",", ":")),
        "--no-session-persistence",
        "--safe-mode",
        "--permission-mode",
        "acceptEdits",
        "--tools",
        "Read",
        "--allowedTools",
        "Read",
        "--max-turns",
        str(config.max_turns),
    ]


def run_structured_teacher(
    config: SonnetCLIConfig,
    *,
    prompt: str,
    schema: Mapping[str, JsonValue],
    working_directory: Path,
) -> SonnetTeacherResult:
    """Execute one structured Sonnet teacher request."""
    completed = subprocess.run(
        build_teacher_command(config, prompt=prompt, schema=schema),
        cwd=working_directory,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=config.timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip()[-500:]
        raise SonnetTeacherError(
            f"Sonnet teacher failed with return code {completed.returncode}: {detail}"
        )
    try:
        envelope = _JSON_OBJECT.validate_json(completed.stdout)
    except ValidationError as error:
        raise SonnetTeacherError("Sonnet teacher returned an invalid JSON envelope") from error
    structured = envelope.get("structured_output")
    if isinstance(structured, dict):
        return SonnetTeacherResult(
            structured_output=structured,
            requested_model=config.model,
        )
    result = envelope.get("result")
    if not isinstance(result, str):
        raise SonnetTeacherError("Sonnet teacher response has no structured output")
    try:
        parsed = _JSON_OBJECT.validate_json(result)
    except ValidationError as error:
        raise SonnetTeacherError("Sonnet teacher result is not a JSON object") from error
    return SonnetTeacherResult(structured_output=parsed, requested_model=config.model)

