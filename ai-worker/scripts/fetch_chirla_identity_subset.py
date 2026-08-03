import argparse
import hashlib
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx2
from chirla_index import parse_chirla_index, safe_relative_path

LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
TARGET_IDENTITIES = {"1", "2", "3", "4", "5", "6", "7", "9", "10", "12", "14"}
DISTRACTOR_IDENTITIES = {"-1", "-2", "-3", "-4", "-5", "-6", "-7", "-8", "-9", "-10", "-11"}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def choose_items(index_path: Path, per_identity: int) -> list[dict[str, str]]:
    items = parse_chirla_index(index_path.read_text(encoding="utf-8"))
    image_items = [
        item
        for item in items
        if item.task == "benchmark"
        and item.scenario == "multi_camera_long_term"
        and item.extension == ".png"
        and item.split in {"train", "test"}
        and item.identity_group_id
    ]
    identities = sorted(
        {item.identity_group_id for item in image_items} | TARGET_IDENTITIES | DISTRACTOR_IDENTITIES
    )
    selected: list[dict[str, str]] = []
    for identity in identities:
        candidates = [item for item in image_items if item.identity_group_id == identity]
        for split in ("train", "test"):
            split_items = [item for item in candidates if item.split == split]
            groups: dict[tuple[str, str, str, str], list] = {}
            for item in split_items:
                key = (item.subset or "", item.sequence_id or "", item.camera_id or "", identity)
                groups.setdefault(key, []).append(item)
            keys = sorted(groups)
            picked = []
            for offset in range(max((len(group) for group in groups.values()), default=0)):
                for key in keys:
                    group = groups[key]
                    if offset < len(group):
                        picked.append(group[offset])
                    if len(picked) >= per_identity:
                        break
                if len(picked) >= per_identity:
                    break
            selected.extend(
                {
                    "url": item.url,
                    "sourcePath": item.relative_path,
                    "localPath": safe_relative_path(item.relative_path),
                    "fileId": item.file_id,
                    "task": item.task,
                    "scenario": item.scenario or "",
                    "split": item.split or "",
                    "subset": item.subset or "",
                    "sequenceId": item.sequence_id or "",
                    "cameraId": item.camera_id or "",
                    "identityGroupId": item.identity_group_id or "",
                    "frameName": item.frame_name or "",
                }
                for item in picked
            )
    return sorted(selected, key=lambda row: str(row["sourcePath"]))


def download(item: dict[str, str], root: Path, client: httpx2.Client) -> dict[str, str | int]:
    target = root / str(item["localPath"])
    target.parent.mkdir(parents=True, exist_ok=True)
    was_existing = target.is_file()
    if not was_existing:
        partial = target.with_suffix(target.suffix + ".part")
        for attempt in range(7):
            try:
                with client.stream("GET", str(item["url"])) as response:
                    if response.status_code in {429, 500, 502, 503, 504}:
                        delay_header = response.headers.get("retry-after", "")
                        try:
                            delay = float(delay_header)
                        except ValueError:
                            delay = 2.0**attempt
                        time.sleep(min(max(delay, 2.0) + random.random(), 45.0))
                        continue
                    response.raise_for_status()
                    with partial.open("wb") as stream:
                        for chunk in response.iter_bytes():
                            stream.write(chunk)
                partial.replace(target)
                break
            except (httpx2.HTTPError, OSError):
                if attempt == 6:
                    raise
                time.sleep(min(2.0**attempt + random.random(), 30.0))
    return {
        **item,
        "license": LICENSE_URL,
        "sha256": digest(target),
        "bytes": target.stat().st_size,
        "status": "existing" if was_existing else "downloaded",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-identity", type=int, default=20)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    selected = choose_items(args.index, args.per_identity)
    limits = httpx2.Limits(
        max_connections=max(1, args.workers),
        max_keepalive_connections=max(1, args.workers),
    )
    timeout = httpx2.Timeout(connect=15.0, read=90.0, write=30.0, pool=30.0)
    transport = httpx2.HTTPTransport(http2=False, retries=2, limits=limits)
    rows = []
    with httpx2.Client(
        transport=transport,
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "qwen3vl-backend-chirla-subset/1.0"},
    ) as client:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            futures = {
                executor.submit(download, item, args.root, client): item for item in selected
            }
            for number, future in enumerate(as_completed(futures), 1):
                item = futures[future]
                try:
                    rows.append(future.result())
                except Exception as error:
                    print(f"failed {item['sourcePath']}: {type(error).__name__}")
                if number % 50 == 0:
                    print(f"processed {number}/{len(selected)}")
    rows.sort(key=lambda row: str(row["sourcePath"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (args.root / "README.source.md").write_text(
        "# CHIRLA identity-heldout subset\n\n"
        f"- selected rows: `{len(selected)}`\n- verified rows: `{len(rows)}`\n"
        "- scenario: `multi_camera_long_term`\n"
        f"- per identity and split target: `{args.per_identity}`\n"
        f"- license: [CC BY 4.0]({LICENSE_URL})\n"
        "- dataset DOI: https://doi.org/10.57760/sciencedb.20543\n\n"
        "This is a public ReID proxy and not a substitute for adjudicated project CCTV data.\n",
        encoding="utf-8",
    )
    print(json.dumps({"selected": len(selected), "verified": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
