import hashlib
import re
import subprocess
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path

_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def _required_text(row: Mapping[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be non-empty text")
    return value


def validate_track_protocol(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, bool]:
    splits_by_identity: dict[str, set[str]] = defaultdict(set)
    cameras_by_track_role: dict[tuple[str, str], dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    signatures_by_track: dict[str, tuple[str, str, str, str, str]] = {}
    for row in rows:
        track_id = _required_text(row, "trackId")
        identity = _required_text(row, "identityGroupId")
        split = _required_text(row, "split")
        role = _required_text(row, "benchmarkRole")
        camera = _required_text(row, "cameraId")
        sequence = _required_text(row, "sequenceId")
        signature = (identity, split, role, camera, sequence)
        previous = signatures_by_track.setdefault(track_id, signature)
        if previous != signature:
            raise ValueError(f"mixed metadata within trackId: {track_id}")
        if split == "train":
            if role != "train":
                raise ValueError("train split requires benchmarkRole=train")
        elif split in {"validation", "test"}:
            if role not in {"query", "gallery"}:
                raise ValueError(
                    f"{split} split requires benchmarkRole=query or gallery"
                )
        else:
            raise ValueError(f"unsupported split: {split}")
        splits_by_identity[identity].add(split)
        cameras_by_track_role[(split, identity)][role].add(camera)

    overlapping = sorted(
        identity
        for identity, splits in splits_by_identity.items()
        if len(splits) > 1
    )
    if overlapping:
        raise ValueError(
            "identity-disjoint split violation: " + ", ".join(overlapping[:10])
        )

    same_camera_pairs = sorted(
        f"{split}:{identity}"
        for (split, identity), cameras in cameras_by_track_role.items()
        if cameras["query"] and not cameras["query"].isdisjoint(cameras["gallery"])
    )
    if same_camera_pairs:
        raise ValueError(
            "cross-camera query/gallery violation: " + ", ".join(same_camera_pairs[:10])
        )

    return {"identityDisjoint": True, "crossCamera": True}


def normalize_sha256(value: str) -> str:
    expected = value.strip().lower()
    if not _SHA256_PATTERN.fullmatch(expected):
        raise ValueError("expected SHA-256 must be 64 lowercase hexadecimal characters")
    return expected


def verify_file_sha256(path: Path, expected_sha256: str) -> str:
    expected = normalize_sha256(expected_sha256)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(
            f"SHA-256 mismatch for {path}: expected {expected}, actual {actual}"
        )
    return actual


def verify_git_checkout(root: Path, expected_commit: str) -> str:
    expected = expected_commit.strip().lower()
    if not _GIT_COMMIT_PATTERN.fullmatch(expected):
        raise ValueError("expected git commit must be 40 lowercase hexadecimal characters")
    actual = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if actual != expected:
        raise ValueError(
            f"CLIP-ReID commit mismatch: expected {expected}, actual {actual}"
        )
    status_lines = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--ignored=matching",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    if status_lines:
        dirty_preview = ", ".join(status_lines[:5])
        raise ValueError(
            "model checkout contains modified, untracked, or ignored runtime files: "
            f"{dirty_preview}"
        )
    return actual


def resolve_clipreid_root(root: Path) -> Path:
    resolved = root.resolve()
    required = (
        resolved / "config",
        resolved / "model",
        resolved / "configs" / "person" / "vit_clipreid.yml",
    )
    missing = [path for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "invalid CLIP-ReID checkout; missing: "
            + ", ".join(str(path) for path in missing)
        )
    return resolved


def require_checkpoint(checkpoint: Path) -> Path:
    resolved = checkpoint.resolve()
    if not resolved.is_file() or resolved.suffix.lower() != ".pth":
        raise FileNotFoundError(f"verified CLIP-ReID .pth checkpoint not found: {resolved}")
    return resolved


def prioritize_checkout(root: Path, module_names: tuple[str, ...]) -> None:
    resolved = str(root.resolve())
    sys.path[:] = [entry for entry in sys.path if str(Path(entry).resolve()) != resolved]
    sys.path.insert(0, resolved)
    for loaded_name in tuple(sys.modules):
        if any(
            loaded_name == module_name or loaded_name.startswith(f"{module_name}.")
            for module_name in module_names
        ):
            del sys.modules[loaded_name]
