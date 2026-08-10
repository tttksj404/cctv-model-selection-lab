from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from scripts.benchmark_chirla_support import (
    ManifestIntegrityError,
    _require_matching_sha256,
)


def test_require_matching_sha256_accepts_unchanged_image(tmp_path: Path) -> None:
    payload = b"verified-frame"
    frame_path = tmp_path / "frame.bin"
    frame_path.write_bytes(payload)
    expected_sha256 = hashlib.sha256(payload).hexdigest()

    actual_sha256 = _require_matching_sha256(
        frame_path,
        expected_sha256,
        "frame.bin",
    )

    assert actual_sha256 == expected_sha256


def test_require_matching_sha256_rejects_changed_image(tmp_path: Path) -> None:
    frame_path = tmp_path / "frame.bin"
    frame_path.write_bytes(b"changed-frame")

    with pytest.raises(ManifestIntegrityError, match="manifest image hash mismatch"):
        _require_matching_sha256(frame_path, "0" * 64, "frame.bin")

