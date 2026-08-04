import json
from pathlib import Path

import pytest

from qwen_backend.sonnet_cli import (
    ClaudeAuthError,
    SonnetCLIConfig,
    build_teacher_command,
    parse_auth_status,
    resolve_claude_executable,
)


def test_resolve_claude_executable_prefers_explicit_file(tmp_path: Path) -> None:
    executable = tmp_path / "claude.exe"
    executable.write_bytes(b"fixture")

    resolved = resolve_claude_executable(executable, environ={}, path_lookup=lambda _: None)

    assert resolved == executable.resolve()


def test_resolve_claude_executable_uses_path_lookup(tmp_path: Path) -> None:
    executable = tmp_path / "claude.exe"
    executable.write_bytes(b"fixture")

    resolved = resolve_claude_executable(
        None,
        environ={},
        path_lookup=lambda command: str(executable) if command == "claude" else None,
    )

    assert resolved == executable.resolve()


def test_auth_status_requires_logged_in_account() -> None:
    raw = json.dumps(
        {
            "loggedIn": False,
            "authMethod": "none",
            "apiProvider": "firstParty",
            "subscriptionType": "team",
        }
    )

    with pytest.raises(ClaudeAuthError, match="not logged in"):
        parse_auth_status(raw)


def test_teacher_command_uses_stable_sonnet_alias_and_read_only_tool(
    tmp_path: Path,
) -> None:
    executable = tmp_path / "claude.exe"
    executable.write_bytes(b"fixture")
    config = SonnetCLIConfig(executable=executable, model="sonnet")

    command = build_teacher_command(
        config,
        prompt="Inspect the person crop.",
        schema={"type": "object", "additionalProperties": False},
    )

    assert command[:3] == [str(executable), "-p", "Inspect the person crop."]
    assert command[command.index("--model") + 1] == "sonnet"
    assert command[command.index("--tools") + 1] == "Read"
    assert "--no-session-persistence" in command
