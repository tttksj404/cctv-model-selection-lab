from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from qwen_backend.worker_protocol import RecordingAnalysisTarget

CacheMode = Literal["full", "segment"]

_WINDOWS_INVALID_FILENAME_CHARS = frozenset('<>:"/\\|?*')
_WINDOWS_RESERVED_BASENAMES = frozenset(
    {
        "AUX",
        "CON",
        "NUL",
        "PRN",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }
)


class RecordingCacheError(RuntimeError):
    """Raised when a completed recording cannot be committed to the cache."""


class RecordingCacheManifest(BaseModel):
    """Immutable metadata proving which source produced one local cache file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    recording_object_key: str = Field(min_length=1, max_length=500)
    recording_file_size_bytes: int | None = Field(default=None, ge=0)
    local_file_size_bytes: int = Field(gt=0)
    mode: CacheMode
    search_from_ms: int | None = Field(default=None, ge=0)
    search_to_ms: int | None = Field(default=None, gt=0)
    complete: bool


@dataclass(frozen=True, slots=True)
class RecordingCachePaths:
    """Video and sidecar paths for one source recording cache entry."""

    video_path: Path
    manifest_path: Path


@dataclass(frozen=True, slots=True)
class RecordingCacheHit:
    """A verified cache file together with the source metadata it contains."""

    video_path: Path
    manifest: RecordingCacheManifest


@dataclass(frozen=True, slots=True)
class RecordingCacheTarget:
    """The source fields needed to identify one cached recording."""

    recording_object_key: str
    recording_file_size_bytes: int | None = None
    search_from_ms: int | None = None
    search_to_ms: int | None = None


CacheTarget = RecordingAnalysisTarget | RecordingCacheTarget


@dataclass(frozen=True, slots=True)
class RecordingCache:
    """Resolves and validates worker-local recording cache entries."""

    root: Path

    def paths(self, target: CacheTarget, mode: CacheMode) -> RecordingCachePaths:
        """Return a stable path derived from the recording object's filename and window."""
        cache_target = _as_cache_target(target)
        recording_filename = _safe_recording_filename(cache_target.recording_object_key)
        start_ms, end_ms = _window_for(cache_target, mode)
        filename = (
            recording_filename
            if mode == "full"
            else _segment_filename(recording_filename, start_ms, end_ms)
        )
        video_path = self.root / "recordings" / filename
        return RecordingCachePaths(video_path, video_path.with_suffix(".manifest.json"))

    def find(self, target: CacheTarget, mode: CacheMode) -> Path | None:
        """Return a verified local path, or None when the cache must be bypassed."""
        hit = self.find_hit(target, mode)
        return hit.video_path if hit is not None else None

    def find_hit(self, target: CacheTarget, mode: CacheMode) -> RecordingCacheHit | None:
        """Find a complete cache entry by source key, regardless of segment window."""
        cache_target = _as_cache_target(target)
        best_hit: RecordingCacheHit | None = None
        for index, paths in enumerate(self._candidate_paths(cache_target, mode)):
            manifest = self._verified_manifest(paths, cache_target, mode)
            if manifest is None:
                continue
            hit = RecordingCacheHit(video_path=paths.video_path, manifest=manifest)
            if index == 0:
                return hit
            if best_hit is None or self._hit_rank(hit, mode) > self._hit_rank(best_hit, mode):
                best_hit = hit
        return best_hit

    def _candidate_paths(
        self,
        target: RecordingCacheTarget,
        mode: CacheMode,
    ) -> tuple[RecordingCachePaths, ...]:
        """Return the canonical path first, then existing manifest-backed entries.

        The canonical filename is preferred for the common path. The manifest scan
        handles files created before the current naming convention or moved by a
        cache cleanup, while still requiring the sidecar to prove source identity.
        """
        expected = self.paths(target, mode)
        candidates: list[RecordingCachePaths] = [expected]
        seen = {expected.manifest_path}
        recordings_dir = self.root / "recordings"
        try:
            manifest_paths = sorted(recordings_dir.glob("*.manifest.json"))
        except OSError:
            return tuple(candidates)
        manifest_suffix = ".manifest.json"
        expected_suffix = expected.video_path.suffix
        for manifest_path in manifest_paths:
            if manifest_path in seen or not manifest_path.is_file():
                continue
            video_stem = manifest_path.name[: -len(manifest_suffix)]
            video_name = f"{video_stem}{expected_suffix}"
            if not video_name:
                continue
            candidates.append(
                RecordingCachePaths(
                    video_path=manifest_path.with_name(video_name),
                    manifest_path=manifest_path,
                )
            )
            seen.add(manifest_path)
        return tuple(candidates)

    @staticmethod
    def _verified_manifest(
        paths: RecordingCachePaths,
        target: RecordingCacheTarget,
        mode: CacheMode,
    ) -> RecordingCacheManifest | None:
        """Validate a candidate without trusting its filename or window suffix."""
        if not paths.video_path.is_file() or not paths.manifest_path.is_file():
            return None
        try:
            manifest = RecordingCacheManifest.model_validate_json(
                paths.manifest_path.read_text(encoding="utf-8")
            )
            local_size = paths.video_path.stat().st_size
        except (OSError, UnicodeDecodeError, ValidationError):
            return None
        if not manifest.complete or local_size != manifest.local_file_size_bytes:
            return None
        if manifest.recording_object_key != target.recording_object_key:
            return None
        if manifest.mode != mode:
            return None
        if mode == "segment" and (manifest.search_from_ms is None or manifest.search_to_ms is None):
            return None
        return manifest

    @staticmethod
    def _hit_rank(hit: RecordingCacheHit, mode: CacheMode) -> tuple[int, int]:
        """Prefer the widest verified segment when several share one source key."""
        if mode == "full":
            return (0, 0)
        start_ms = hit.manifest.search_from_ms or 0
        end_ms = hit.manifest.search_to_ms or start_ms
        return (end_ms - start_ms, -start_ms)

    def store(
        self,
        target: CacheTarget,
        mode: CacheMode,
        video_path: Path,
    ) -> Path:
        """Write a manifest only after the downloaded video is complete."""
        cache_target = _as_cache_target(target)
        paths = self.paths(cache_target, mode)
        if video_path != paths.video_path:
            raise RecordingCacheError("download destination does not match recording cache path")
        try:
            local_size = video_path.stat().st_size
        except OSError as error:
            raise RecordingCacheError("downloaded recording is not readable") from error
        if local_size <= 0:
            raise RecordingCacheError("downloaded recording is empty")
        if (
            mode == "full"
            and cache_target.recording_file_size_bytes is not None
            and local_size != cache_target.recording_file_size_bytes
        ):
            raise RecordingCacheError("downloaded recording size does not match central target")
        start_ms, end_ms = _window_for(cache_target, mode)
        manifest = RecordingCacheManifest(
            recording_object_key=cache_target.recording_object_key,
            recording_file_size_bytes=cache_target.recording_file_size_bytes,
            local_file_size_bytes=local_size,
            mode=mode,
            search_from_ms=start_ms,
            search_to_ms=end_ms,
            complete=True,
        )
        paths.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = paths.manifest_path.with_name(f".{paths.manifest_path.name}.part")
        try:
            temporary_path.write_text(manifest.model_dump_json(), encoding="utf-8")
            temporary_path.replace(paths.manifest_path)
        except OSError as error:
            raise RecordingCacheError("recording cache manifest could not be committed") from error
        finally:
            temporary_path.unlink(missing_ok=True)
        return video_path


def _as_cache_target(target: CacheTarget) -> RecordingCacheTarget:
    if isinstance(target, RecordingCacheTarget):
        return target
    return RecordingCacheTarget(
        recording_object_key=target.recording_object_key,
        recording_file_size_bytes=target.recording_file_size_bytes,
        search_from_ms=target.search_from_ms,
        search_to_ms=target.search_to_ms,
    )


def _safe_recording_filename(recording_object_key: str) -> str:
    """Use a safe object-key basename, with a deterministic fallback if needed."""
    candidate = PurePosixPath(recording_object_key.replace("\\", "/")).name
    if _is_safe_windows_filename(candidate):
        return candidate
    key_hash = hashlib.sha256(recording_object_key.encode("utf-8")).hexdigest()
    return f"recording-{key_hash}.mp4"


def _is_safe_windows_filename(candidate: str) -> bool:
    """Return whether a basename can be materialized safely on Windows."""
    if not candidate or candidate in {".", ".."} or len(candidate) > 180:
        return False
    if candidate != candidate.rstrip(" ."):
        return False
    if any(
        ord(character) < 32 or character in _WINDOWS_INVALID_FILENAME_CHARS
        for character in candidate
    ):
        return False
    basename = candidate.split(".", maxsplit=1)[0].upper()
    return basename not in _WINDOWS_RESERVED_BASENAMES


def _segment_filename(filename: str, start_ms: int | None, end_ms: int | None) -> str:
    """Add the requested window while retaining the source recording filename."""
    if start_ms is None or end_ms is None:
        raise RecordingCacheError("segment cache requires a validated time window")
    suffix = PurePosixPath(filename).suffix
    if not suffix:
        return f"{filename}__{start_ms}-{end_ms}.window.mp4"
    stem = filename[: -len(suffix)]
    return f"{stem}__{start_ms}-{end_ms}.window{suffix}"


def _window_for(
    target: RecordingCacheTarget,
    mode: CacheMode,
) -> tuple[int | None, int | None]:
    """Return the cache identity window for full or segmented media."""
    if mode == "full":
        return None, None
    return target.search_from_ms, target.search_to_ms

