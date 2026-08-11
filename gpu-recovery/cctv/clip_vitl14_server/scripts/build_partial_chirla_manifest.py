from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, "scripts")
from chirla_index import parse_chirla_index, safe_relative_path, select_reid_files

root = Path("experiments/data/chirla")
files = parse_chirla_index((root / "source_url_index_v2.txt").read_text(encoding="utf-8"))
selected = select_reid_files(files, scenario="multi_camera_long_term", max_files=1500)
rows = []
for item in selected:
    if item.extension not in {".png", ".json"}:
        continue
    target = root / safe_relative_path(item.relative_path)
    if not target.is_file():
        continue
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    rows.append({
        "sourcePath": item.relative_path,
        "localPath": safe_relative_path(item.relative_path),
        "fileId": item.file_id,
        "sha256": digest,
        "bytes": target.stat().st_size,
        "status": "partial-existing",
        "dataset": "CHIRLA",
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "sourceIndexUrl": "https://www.scidb.cn/api/sdb-filetree-service/getAllUrl",
        "task": item.task,
        "scenario": item.scenario or "",
        "split": item.split or "",
        "subset": item.subset or "",
        "sequenceId": item.sequence_id or "",
        "cameraId": item.camera_id or "",
        "identityGroupId": item.identity_group_id or "",
        "frameName": item.frame_name or "",
    })
rows.sort(key=lambda row: str(row["sourcePath"]))
(root / "download_manifest.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
print(json.dumps({"selected": len(selected), "present": len(rows), "identities": len({str(row["identityGroupId"]) for row in rows if str(row["sourcePath"]).endswith(".png")})}))
