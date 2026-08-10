from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Protocol, TypedDict, cast


class ModelStorageConfig(Protocol):
    @property
    def model_directory(self) -> str: ...

    @property
    def model_manifest(self) -> str: ...


class RealtimeModelConfig(ModelStorageConfig, Protocol):
    @property
    def yolo_weights(self) -> str: ...


class SoliderModelConfig(ModelStorageConfig, Protocol):
    @property
    def solider_checkpoint(self) -> str: ...


class ModelWeightError(RuntimeError):
    pass


class _ModelEntry(TypedDict):
    sha256: str


class _ModelManifest(TypedDict):
    models: dict[str, _ModelEntry]


def _verified_model_file(
    config: ModelStorageConfig,
    candidate_value: str,
    *,
    model_kind: str,
) -> str:
    project_root = Path.cwd().resolve()
    model_directory = (project_root / config.model_directory).resolve()
    candidate = Path(candidate_value)
    weights_path = (
        candidate.resolve()
        if candidate.is_absolute()
        else (project_root / candidate).resolve()
    )
    if not weights_path.is_relative_to(model_directory):
        raise ModelWeightError(f"{model_kind}_weights_outside_trusted_model_directory")
    if not weights_path.is_file():
        raise ModelWeightError(f"trusted_{model_kind}_weights_missing: {weights_path.name}")

    manifest_path = (project_root / config.model_manifest).resolve()
    manifest = cast(
        _ModelManifest,
        json.loads(manifest_path.read_text(encoding="utf-8")),
    )
    try:
        model_entry = manifest["models"][weights_path.name]
        expected_sha256 = model_entry["sha256"]
    except (KeyError, TypeError) as error:
        raise ModelWeightError(
            f"{model_kind}_weights_not_in_manifest: {weights_path.name}"
        ) from error
    if len(expected_sha256) != 64:
        raise ModelWeightError("invalid_model_manifest_sha256")

    with weights_path.open("rb") as weights_file:
        actual_sha256 = hashlib.file_digest(weights_file, "sha256").hexdigest()
    if actual_sha256.lower() != expected_sha256.lower():
        raise ModelWeightError(f"{model_kind}_weights_sha256_mismatch: {weights_path.name}")
    return str(weights_path)


def verified_yolo_weights(config: RealtimeModelConfig) -> str:
    return _verified_model_file(config, config.yolo_weights, model_kind="yolo")


def verified_solider_checkpoint(config: SoliderModelConfig) -> str:
    return _verified_model_file(
        config,
        config.solider_checkpoint,
        model_kind="solider",
    )

