from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path

IMAGE_SUFFIXES = frozenset({".bmp", ".jpeg", ".jpg", ".png"})


@dataclass(frozen=True, slots=True)
class SplitConfig:
    train_identities: int = 80
    validation_identities: int = 20
    shared_identities: int = 200
    validation_distractor_fraction: float = 0.2


@dataclass(frozen=True, slots=True)
class PridRecord:
    schemaVersion: str
    dataset: str
    task: str
    evaluationScope: str
    split: str
    benchmarkRole: str
    cameraId: str
    sequenceId: str
    identityGroupId: str
    identityKind: str
    trackId: str
    localPath: str
    sha256: str
    labelSource: str
    identityIsProjectReviewed: bool
    domainStatus: str


def _identity_dirs(camera_root: Path) -> dict[int, Path]:
    identities: dict[int, Path] = {}
    for path in camera_root.iterdir():
        if not path.is_dir():
            continue
        match = re.search(r"(\d+)$", path.name)
        if match is None:
            continue
        identity = int(match.group(1))
        identities[identity] = path
    return identities


def _images(identity_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in identity_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _validation_count(size: int, fraction: float) -> int:
    if size < 2:
        return size
    return min(size - 1, max(1, math.ceil(size * fraction)))


def _record(
    data_root: Path,
    image: Path,
    *,
    split: str,
    role: str,
    camera: str,
    identity: str,
    identity_kind: str,
) -> PridRecord:
    track_id = f"{split}:{camera}:{identity}"
    return PridRecord(
        schemaVersion="prid2011-cross-camera-track-v1",
        dataset="PRID2011 multi-shot",
        task="video-person-reidentification",
        evaluationScope="public-cross-camera-identity-disjoint-track-heldout",
        split=split,
        benchmarkRole=role,
        cameraId=camera,
        sequenceId=track_id,
        identityGroupId=identity,
        identityKind=identity_kind,
        trackId=track_id,
        localPath=image.relative_to(data_root).as_posix(),
        sha256=_sha256(image),
        labelSource="official PRID2011 camera-directory identity annotation",
        identityIsProjectReviewed=False,
        domainStatus="public-CCTV-proxy-not-project-CCTV",
    )


def build_records(data_root: Path, config: SplitConfig) -> list[dict[str, object]]:
    if config.train_identities < 1 or config.validation_identities < 1:
        raise ValueError("train and validation identity counts must be positive")
    if not 0.0 < config.validation_distractor_fraction < 1.0:
        raise ValueError("validation distractor fraction must be between zero and one")

    camera_dirs = {
        "cam_a": _identity_dirs(data_root / "cam_a"),
        "cam_b": _identity_dirs(data_root / "cam_b"),
    }
    shared = sorted(set(camera_dirs["cam_a"]) & set(camera_dirs["cam_b"]))[
        : config.shared_identities
    ]
    minimum = config.train_identities + config.validation_identities + 1
    if len(shared) < minimum:
        raise ValueError(
            f"at least {minimum} shared identities are required, found {len(shared)}"
        )

    train_end = config.train_identities
    validation_end = train_end + config.validation_identities
    splits = {
        "train": shared[:train_end],
        "validation": shared[train_end:validation_end],
        "test": shared[validation_end:],
    }
    records: list[PridRecord] = []
    for split, identities in splits.items():
        for identity_number in identities:
            identity = f"prid-shared-{identity_number:03d}"
            for camera, role in (
                ("cam_a", "train" if split == "train" else "query"),
                ("cam_b", "train" if split == "train" else "gallery"),
            ):
                for image in _images(camera_dirs[camera][identity_number]):
                    records.append(
                        _record(
                            data_root,
                            image,
                            split=split,
                            role=role,
                            camera=camera,
                            identity=identity,
                            identity_kind="shared-target",
                        )
                    )

    shared_set = set(shared)
    for camera, role in (("cam_a", "query"), ("cam_b", "gallery")):
        exclusive = sorted(set(camera_dirs[camera]) - shared_set)
        validation_size = _validation_count(
            len(exclusive), config.validation_distractor_fraction
        )
        for index, identity_number in enumerate(exclusive):
            split = "validation" if index < validation_size else "test"
            identity = f"prid-{camera.replace('_', '-')}-only-{identity_number:03d}"
            for image in _images(camera_dirs[camera][identity_number]):
                records.append(
                    _record(
                        data_root,
                        image,
                        split=split,
                        role=role,
                        camera=camera,
                        identity=identity,
                        identity_kind="distractor",
                    )
                )
    return [asdict(record) for record in sorted(records, key=lambda item: item.localPath)]


def _find_multishot_root(extracted_root: Path) -> Path:
    matches = [
        path.parent
        for path in extracted_root.rglob("cam_a")
        if path.is_dir() and (path.parent / "cam_b").is_dir()
    ]
    if not matches:
        raise FileNotFoundError("could not find sibling cam_a and cam_b directories")
    multi_shot = [path for path in matches if "multi" in path.as_posix().lower()]
    return sorted(multi_shot or matches, key=lambda path: len(path.parts))[0]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a strict PRID2011 cross-camera track-heldout manifest"
    )
    parser.add_argument("--extracted-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--train-identities", type=int, default=80)
    parser.add_argument("--validation-identities", type=int, default=20)
    parser.add_argument("--shared-identities", type=int, default=200)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    data_root = _find_multishot_root(args.extracted_root)
    config = SplitConfig(
        train_identities=args.train_identities,
        validation_identities=args.validation_identities,
        shared_identities=args.shared_identities,
    )
    records = build_records(data_root, config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in records),
        encoding="utf-8",
    )
    summary = {
        "schemaVersion": "prid2011-cross-camera-track-v1",
        "dataRoot": str(data_root),
        "records": len(records),
        "tracks": len({str(row["trackId"]) for row in records}),
        "splits": {
            split: sum(row["split"] == split for row in records)
            for split in ("train", "validation", "test")
        },
        "strictCrossCameraGeneralizationEvidence": True,
        "projectCctvPromotionEvidence": False,
    }
    args.output.with_suffix(".summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
