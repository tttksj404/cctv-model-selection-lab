# /// script
# requires-python = ">=3.11"
# dependencies = ["huggingface_hub"]
# ///
from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download


class DownloadRuntimeError(RuntimeError):
    pass


def download(repo_id: str, output_dir: Path, status_path: Path, workers: int) -> dict[str, int | str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    files = [
        name for name in HfApi().list_repo_files(repo_id=repo_id, repo_type="dataset")
        if name.lower().endswith(".png")
    ]
    if not files:
        raise DownloadRuntimeError("repository contains no PNG files")

    def one(name: str) -> int:
        output = output_dir / Path(name).name
        if output.is_file():
            return 0
        cached = Path(hf_hub_download(repo_id=repo_id, repo_type="dataset", filename=name, local_dir=str(output_dir)))
        cached.replace(output)
        return 1

    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(one, name): name for name in files if not (output_dir / Path(name).name).is_file()}
        for future in as_completed(futures):
            name = futures[future]
            future.result()
            completed += 1
            if completed % 25 == 0 or completed == len(futures):
                print(f"downloaded_missing={completed}/{len(futures)} file={Path(name).name}", flush=True)
    result: dict[str, int | str] = {
        "status": "DOWNLOAD_DONE",
        "repo_id": repo_id,
        "remote_png_count": len(files),
        "local_png_count": len(list(output_dir.glob("*.png"))),
        "workers": workers,
    }
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", default="Simuletic/CCTV-Pedestrian-1K-Person-Attribute-Dataset")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--status-path", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if args.workers < 1 or args.workers > 16:
        raise DownloadRuntimeError("workers must be between 1 and 16")
    print(json.dumps(download(args.repo_id, args.output_dir.resolve(), args.status_path.resolve(), args.workers), ensure_ascii=False))


if __name__ == "__main__":
    main()

