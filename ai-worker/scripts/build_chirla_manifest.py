from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
ManifestValue = str | int
ManifestRow = dict[str, ManifestValue]


@dataclass(frozen=True, slots=True)
class ChirlaIdentityRecord:
    schemaVersion: str
    dataset: str
    license: str
    task: str
    scenario: str
    benchmarkRole: str
    split: str
    subset: str
    sequenceId: str
    cameraId: str
    identityGroupId: str
    frameName: str
    sourcePath: str
    localPath: str
    sourceFileId: str
    sha256: str
    bytes: int
    labelSource: str
    identityIsProjectReviewed: bool
    domainStatus: str


def _text(row: Mapping[str, ManifestValue], key: str) -> str:
    value = row.get(key, "")
    if not isinstance(value, str):
        raise ValueError(f"manifest field {key} must be text")
    return value


def _number(row: Mapping[str, ManifestValue], key: str) -> int:
    value = row.get(key, 0)
    if not isinstance(value, int):
        raise ValueError(f"manifest field {key} must be an integer")
    return value


def benchmark_role(split: str, subset: str) -> str:
    if split == "train" and subset == "train_0":
        return "train"
    if split == "test" and subset == "test_0":
        return "validation"
    if split == "train":
        return "gallery"
    if split == "test":
        return "query"
    raise ValueError(f"unsupported CHIRLA benchmark split: {split}")


def build_records(rows: list[ManifestRow]) -> list[ChirlaIdentityRecord]:
    records: list[ChirlaIdentityRecord] = []
    for row in rows:
        if _text(row, "sourcePath").lower().endswith(".json"):
            continue
        split = _text(row, "split")
        subset = _text(row, "subset")
        records.append(
            ChirlaIdentityRecord(
                schemaVersion="chirla-project-reid-v1",
                dataset="CHIRLA",
                license=LICENSE_URL,
                task="person-reidentification",
                scenario=_text(row, "scenario"),
                benchmarkRole=benchmark_role(split, subset),
                split=split,
                subset=subset,
                sequenceId=_text(row, "sequenceId"),
                cameraId=_text(row, "cameraId"),
                identityGroupId=_text(row, "identityGroupId"),
                frameName=_text(row, "frameName"),
                sourcePath=_text(row, "sourcePath"),
                localPath=_text(row, "localPath"),
                sourceFileId=_text(row, "fileId"),
                sha256=_text(row, "sha256"),
                bytes=_number(row, "bytes"),
                labelSource="official CHIRLA benchmark image-directory identity label",
                identityIsProjectReviewed=False,
                domainStatus="public-proxy-not-project-CCTV-review",
            )
        )
    return sorted(records, key=lambda record: record.sourcePath)


def _load_rows(path: Path) -> list[ManifestRow]:
    return [
        cast(ManifestRow, json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, records: list[ChirlaIdentityRecord]) -> None:
    content = "".join(
        json.dumps(asdict(record), ensure_ascii=False, sort_keys=True) + "\n"
        for record in records
    )
    path.write_text(content, encoding="utf-8")


def main() -> None:
    root = Path("experiments/data/chirla")
    records = build_records(_load_rows(root / "download_manifest.jsonl"))
    _write_jsonl(root / "chirla_identity_manifest.jsonl", records)
    summary = {
        "schemaVersion": "chirla-project-reid-v1",
        "records": len(records),
        "benchmarkRoles": sorted({record.benchmarkRole for record in records}),
        "identities": sorted({record.identityGroupId for record in records}),
        "sequences": sorted({record.sequenceId for record in records}),
        "cameras": sorted({record.cameraId for record in records}),
        "identityReviewStatus": "source-annotated-not-project-reviewed",
        "license": LICENSE_URL,
    }
    (root / "chirla_identity_manifest.summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"saved {len(records)} identity records")


if __name__ == "__main__":
    main()
