from __future__ import annotations
import hashlib, json, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests
from chirla_index import parse_chirla_index, safe_relative_path, select_reid_files
ROOT=Path("experiments/data/chirla")

def fetch(item):
    target=ROOT/safe_relative_path(item.relative_path); target.parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():
        part=target.with_suffix(target.suffix+".part")
        for attempt in range(4):
            try:
                response=requests.get(item.url,timeout=(10,60),stream=True)
                if response.status_code in {429,500,502,503,504}:
                    response.close(); time.sleep(min(2**attempt,15)); continue
                response.raise_for_status()
                with part.open("wb") as out:
                    for chunk in response.iter_content(1024*1024):
                        if chunk: out.write(chunk)
                part.replace(target); break
            except (requests.RequestException,OSError):
                if attempt==3: raise
                time.sleep(min(2**attempt,15))
    return target
root=ROOT; root.mkdir(parents=True,exist_ok=True)
files=parse_chirla_index((root/"source_url_index_v2.txt").read_text(encoding="utf-8"))
selected=[i for i in select_reid_files(files,scenario="multi_camera_long_term",max_files=1500) if i.split=="train"]
with ThreadPoolExecutor(max_workers=8) as pool:
    futures=[pool.submit(fetch,item) for item in selected]
    for n,future in enumerate(as_completed(futures),1):
        future.result()
        if n%50==0: print(f"train {n}/{len(selected)}",flush=True)
print(f"train_done {len(selected)}")
