import json
import os
import subprocess
import sys
from pathlib import Path


def run_module(
    *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    process_env = os.environ.copy()
    if env is not None:
        process_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", *args],
        capture_output=True,
        text=True,
        check=False,
        env=process_env,
    )


def test_distillation_cli_help() -> None:
    result = run_module("qwen_backend.distillation_cli", "--help")
    assert result.returncode == 0
    assert "validate" in result.stdout
    assert "prepare" in result.stdout


def test_annotation_and_prepare_cli_round_trip(tmp_path: Path) -> None:
    image_root = tmp_path / "images"
    image = image_root / "cam01" / "000001.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"qa-image")
    annotations = tmp_path / "annotations.jsonl"
    prepared = tmp_path / "qwen.jsonl"

    annotation = run_module(
        "qwen_backend.annotation_cli",
        "--image",
        str(image),
        "--image-root",
        str(image_root),
        "--sample-id",
        "qa-001",
        "--teacher-model",
        "local",
        "--decision",
        "match",
        "--confidence",
        "0.9",
        "--approval-status",
        "approved",
        "--reviewed-by",
        "qa-fixture",
        "--color",
        "red",
        "--clothing",
        "jacket",
        "--object-name",
        "person",
        "--bbox",
        "1",
        "2",
        "40",
        "80",
        "--output",
        str(annotations),
    )
    assert annotation.returncode == 0, annotation.stderr

    validation = run_module(
        "qwen_backend.distillation_cli",
        "validate",
        "--input",
        str(annotations),
        "--image-root",
        str(image_root),
    )
    assert validation.returncode == 0, validation.stderr
    assert json.loads(validation.stdout)["status"] == "valid"

    preparation = run_module(
        "qwen_backend.distillation_cli",
        "prepare",
        "--input",
        str(annotations),
        "--image-root",
        str(image_root),
        "--output",
        str(prepared),
    )
    assert preparation.returncode == 0, preparation.stderr
    record = json.loads(prepared.read_text(encoding="utf-8"))
    assert record["image"] == "cam01/000001.jpg"
    assert record["conversations"][0]["from"] == "human"


def test_validation_cli_rejects_changed_image(tmp_path: Path) -> None:
    image_root = tmp_path / "images"
    image = image_root / "candidate.png"
    image_root.mkdir()
    image.write_bytes(b"original")
    annotations = tmp_path / "annotations.jsonl"

    annotation = run_module(
        "qwen_backend.annotation_cli",
        "--image",
        str(image),
        "--image-root",
        str(image_root),
        "--sample-id",
        "qa-002",
        "--teacher-model",
        "local",
        "--decision",
        "review",
        "--confidence",
        "0.5",
        "--output",
        str(annotations),
    )
    assert annotation.returncode == 0, annotation.stderr
    image.write_bytes(b"changed")

    validation = run_module(
        "qwen_backend.distillation_cli",
        "validate",
        "--input",
        str(annotations),
        "--image-root",
        str(image_root),
    )
    assert validation.returncode == 2
    assert "source hash mismatch" in validation.stderr


def test_skip_hash_is_rejected_in_production(tmp_path: Path) -> None:
    result = run_module(
        "qwen_backend.distillation_cli",
        "validate",
        "--input",
        str(tmp_path / "annotations.jsonl"),
        "--image-root",
        str(tmp_path),
        "--skip-hash",
        env={"QWEN_ENVIRONMENT": "production"},
    )

    assert result.returncode == 2
    assert "skip-hash is disabled in production" in result.stderr
