#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import parse_qs, unquote, urlsplit

CHIRLA_PREFIX = "/V2/CHIRLA_dataset/"


@dataclass(frozen=True, slots=True)
class ChirlaRemoteFile:
    url: str
    file_id: str
    relative_path: str
    extension: str
    task: str
    scenario: str | None
    split: str | None
    subset: str | None
    sequence_id: str | None
    camera_id: str | None
    identity_group_id: str | None
    frame_name: str | None


def _first(query: dict[str, list[str]], name: str) -> str | None:
    values = query.get(name, [])
    return values[0] if values else None


def _camera_name(path: str) -> str | None:
    stem = PurePosixPath(path).stem
    return stem if stem.startswith("camera_") else None


def parse_chirla_url(raw_url: str) -> ChirlaRemoteFile | None:
    parsed = urlsplit(raw_url.strip())
    query = parse_qs(parsed.query)
    file_id = _first(query, "fileId")
    encoded_path = _first(query, "path")
    if not file_id or not encoded_path:
        return None
    dataset_path = unquote(encoded_path)
    if not dataset_path.startswith(CHIRLA_PREFIX):
        return None
    relative_path = dataset_path.removeprefix(CHIRLA_PREFIX)
    parts = relative_path.split("/")
    extension = PurePosixPath(relative_path).suffix.lower()
    task = parts[0] if parts else ""
    scenario: str | None = None
    split: str | None = None
    subset: str | None = None
    sequence_id: str | None = None
    camera_id: str | None = None
    identity_group_id: str | None = None
    frame_name: str | None = None

    match task:
        case "benchmark":
            if len(parts) < 3:
                return None
            scenario = parts[2]
            if len(parts) >= 4:
                split = parts[3]
            if len(parts) >= 5 and parts[1] == "reid":
                subset = parts[4]
            if len(parts) >= 6 and parts[1] == "reid":
                sequence_id = parts[5]
            if extension == ".png" and len(parts) >= 4:
                identity_group_id = parts[-2]
                frame_name = parts[-1]
                camera_id = parts[-3] if len(parts) >= 3 else None
            elif extension == ".json":
                camera_id = _camera_name(parts[-1])
        case "annotations":
            sequence_id = parts[1] if len(parts) >= 2 else None
            camera_id = _camera_name(parts[-1]) if parts else None
        case "videos":
            sequence_id = parts[1] if len(parts) >= 2 else None
            camera_id = _camera_name(parts[-1]) if parts else None
        case _:
            return None

    return ChirlaRemoteFile(
        url=raw_url.strip(),
        file_id=file_id,
        relative_path=relative_path,
        extension=extension,
        task=task,
        scenario=scenario,
        split=split,
        subset=subset,
        sequence_id=sequence_id,
        camera_id=camera_id,
        identity_group_id=identity_group_id,
        frame_name=frame_name,
    )


def parse_chirla_index(content: str) -> tuple[ChirlaRemoteFile, ...]:
    entries = tuple(
        entry
        for line in content.splitlines()
        if (entry := parse_chirla_url(line)) is not None
    )
    return tuple(sorted(entries, key=lambda item: item.relative_path))


def select_reid_files(
    files: tuple[ChirlaRemoteFile, ...],
    *,
    scenario: str,
    max_files: int = 0,
) -> tuple[ChirlaRemoteFile, ...]:
    candidates = tuple(
        item
        for item in files
        if item.task == "benchmark"
        and item.scenario == scenario
        and item.extension in {".png", ".json"}
    )
    if max_files <= 0 or len(candidates) <= max_files:
        return candidates
    metadata = tuple(item for item in candidates if item.extension == ".json")
    images = tuple(item for item in candidates if item.extension == ".png")
    image_budget = max(max_files - len(metadata), 0)
    if image_budget == 0:
        return metadata[:max_files]
    groups: defaultdict[tuple[str, str], list[ChirlaRemoteFile]] = defaultdict(list)
    for image in images:
        groups[(image.subset or "", image.identity_group_id or "")].append(image)
    keys = sorted(groups)
    sampled: list[ChirlaRemoteFile] = []
    for index in range(max((len(group) for group in groups.values()), default=0)):
        for key in keys:
            group = groups[key]
            if index < len(group):
                sampled.append(group[index])
            if len(sampled) == image_budget:
                break
        if len(sampled) == image_budget:
            break
    return tuple(sorted((*metadata, *sampled), key=lambda item: item.relative_path))


def safe_relative_path(relative_path: str) -> str:
    return relative_path.replace(":", "-")
