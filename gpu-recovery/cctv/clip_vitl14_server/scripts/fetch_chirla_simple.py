from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from chirla_index import parse_chirla_index, safe_relative_path, select_reid_files

ROOT = Path("experiments/data/chirla")
SCENARIO = "multi_camera_long_term"
MAX_FILES = 1500
WORKERS = 8


def download(item: object) -> dict[str, str | int]:
    relative_path = safe_relative_path(item.relative_path)  # type: ignore[attr-defined]
    target = ROOT / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    status = "existing"
    if not target.exists():
        partial = target.with_suffix(target.suffix + ".part")
        for attempt in range(4):
            try:
                response = requests.get(item.url, timeout=(10, 60), stream=True)  # type: ignore[attr-defined]
                if response.status_code in {429, 500, 502, 503, 504}:
                    response.close()
                    time.sleep(min(2 ** attempt, 15))
                    continue
                response.raise_for_status()
                with partial.open("wb") as stream:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            stream.write(chunk)
                partial.replace(target)
                status = "downloaded"
                break
            except (requests.RequestException, OSError):
                if attempt == 3:
                    raise
                time.sleep(min(2 ** attempt, 15))
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return {
        "sourcePath": item.relative_path,  # type: ignore[attr-defined]
        "localPath": relative_path,
        "fileId": item.file_id,  # type: ignore[attr-defined]
        "sha256": digest,
        "bytes": target.stat().st_size,
        "status": status,
        "dataset": "CHIRLA",
        "scenario": item.scenario or "",  # type: ignore[attr-defined]
        "split": item.split or "",  # type: ignore[attr-defined]
        "subset": item.subset or "",  # type: ignore[attr-defined]
        "sequenceId": item.sequence_id or "",  # type: ignore[attr-defined]
        "cameraId": item.camera_id or "",  # type: ignore[attr-defined]
        "identityGroupId": item.identity_group_id or "",  # type: ignore[attr-defined]
        "frameName": item.frame_name or "",  # type: ignore[attr-defined]
    }


ROOT.mkdir(parents=True, exist_ok=True)
files = parse_chirla_index((ROOT / "source_url_index_v2.txt").read_text(encoding="utf-8"))
selected = select_reid_files(files, scenario=SCENARIO, max_files=MAX_FILES)
rows: list[dict[str, str | int]] = []
with ThreadPoolExecutor(max_workers=WORKERS) as executor:
    futures = [executor.submit(download, item) for item in selected]
    for number, future in enumerate(as_completed(futures), start=1):
        rows.append(future.result())
        if number % 100 == 0:
            print(f"processed {number}/{len(selected)}", flush=True)
rows.sort(key=lambda row: str(row["sourcePath"]))
(ROOT / "download_manifest.jsonl").write_text(
    "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    encoding="utf-8",
)
print(f"saved {len(rows)}/{len(selected)}")
