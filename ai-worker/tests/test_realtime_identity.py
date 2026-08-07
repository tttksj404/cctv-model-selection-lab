import subprocess
from pathlib import Path

import pytest

import qwen_backend.realtime_identity as realtime_identity
from qwen_backend.realtime_identity import (
    validate_reference_image,
    verified_solider_root,
)
from qwen_backend.realtime_models import ReferenceImageError, SoliderCheckoutError


def test_synthetic_head_file_cannot_impersonate_verified_checkout(tmp_path: Path) -> None:
    fake_root = tmp_path / "fake-solider"
    (fake_root / ".git").mkdir(parents=True)
    (fake_root / ".git" / "HEAD").write_text(
        "8c08e1c3255e8e1e51e006bf189e52cc57b009ed",
        encoding="utf-8",
    )

    with pytest.raises(SoliderCheckoutError, match="검증 실패"):
        verified_solider_root(str(fake_root))


def test_non_image_reference_is_rejected_before_model_loading(tmp_path: Path) -> None:
    invalid_image = tmp_path / "not-an-image.jpg"
    invalid_image.write_text("not image bytes", encoding="utf-8")

    with pytest.raises(ReferenceImageError, match="기준 사진"):
        validate_reference_image(invalid_image)


def test_generated_python_bytecode_does_not_make_checkout_dirty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkout = tmp_path / "solider"
    cache = checkout / "config" / "__pycache__"
    cache.mkdir(parents=True)
    config = checkout / "configs" / "msmt17" / "swin_base.yml"
    config.parent.mkdir(parents=True)
    config.write_text("MODEL: {}", encoding="utf-8")
    tracked = cache / "__init__.cpython-37.pyc"
    generated = cache / "__init__.cpython-312.pyc"
    tracked.write_bytes(b"official")

    subprocess.run(("git", "init", str(checkout)), check=True, capture_output=True)
    subprocess.run(
        ("git", "-C", str(checkout), "config", "user.email", "tests@eyesonu.local"),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ("git", "-C", str(checkout), "config", "user.name", "EYES ON U Tests"),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ("git", "-C", str(checkout), "config", "core.autocrlf", "false"),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ("git", "-C", str(checkout), "add", str(tracked), str(config)),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ("git", "-C", str(checkout), "commit", "-m", "fixture"),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        (
            "git",
            "-C",
            str(checkout),
            "remote",
            "add",
            "origin",
            realtime_identity.SOLIDER_REMOTE,
        ),
        check=True,
        capture_output=True,
    )
    commit = subprocess.run(
        ("git", "-C", str(checkout), "rev-parse", "HEAD"),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    monkeypatch.setattr(realtime_identity, "SOLIDER_COMMIT", commit)
    generated.write_bytes(b"generated")

    assert verified_solider_root(str(checkout)) == checkout.resolve()

    assert tracked.read_bytes() == b"official"
    assert generated.read_bytes() == b"generated"

    untracked_source = checkout / "config" / "generated.py"
    untracked_source.write_text("# unexpected source", encoding="utf-8")
    with pytest.raises(SoliderCheckoutError, match="working tree is not clean"):
        verified_solider_root(str(checkout))


def test_checkout_validation_disables_repository_fsmonitor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checkout = tmp_path / "solider"
    config = checkout / "configs" / "msmt17" / "swin_base.yml"
    config.parent.mkdir(parents=True)
    config.write_text("MODEL: {}", encoding="utf-8")
    marker = tmp_path / "fsmonitor-ran.txt"
    monitor = checkout / "fsmonitor.sh"
    monitor.write_text(
        f"#!/bin/sh\nprintf ran > '{marker.as_posix()}'\n",
        encoding="utf-8",
    )
    monitor.chmod(0o755)

    subprocess.run(("git", "init", str(checkout)), check=True, capture_output=True)
    subprocess.run(
        ("git", "-C", str(checkout), "config", "user.email", "tests@eyesonu.local"),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ("git", "-C", str(checkout), "config", "user.name", "EYES ON U Tests"),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ("git", "-C", str(checkout), "config", "core.autocrlf", "false"),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ("git", "-C", str(checkout), "add", str(config), str(monitor)),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ("git", "-C", str(checkout), "commit", "-m", "fixture"),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        (
            "git",
            "-C",
            str(checkout),
            "remote",
            "add",
            "origin",
            realtime_identity.SOLIDER_REMOTE,
        ),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ("git", "-C", str(checkout), "config", "core.fsmonitor", str(monitor)),
        check=True,
        capture_output=True,
    )
    commit = subprocess.run(
        ("git", "-C", str(checkout), "rev-parse", "HEAD"),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    monkeypatch.setattr(realtime_identity, "SOLIDER_COMMIT", commit)

    verified_solider_root(str(checkout))

    assert not marker.exists()
