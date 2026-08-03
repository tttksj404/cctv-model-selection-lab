import argparse
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from huggingface_hub import HfApi, hf_hub_download

TARGET_IDENTITIES = ("1", "2", "3", "4", "5", "6", "7", "9", "10", "12", "14")
DISTRACTOR_IDENTITIES = ("-1", "-2", "-3", "-4", "-5", "-6", "-7", "-8", "-9", "-10", "-11")
REPO_ID = "adonaivera/fiftyone-multiview-reid-attributes"


def map_identity(source_id: int) -> str:
    if source_id < len(TARGET_IDENTITIES):
        return TARGET_IDENTITIES[source_id]
    if source_id < len(TARGET_IDENTITIES) + len(DISTRACTOR_IDENTITIES):
        return DISTRACTOR_IDENTITIES[source_id - len(TARGET_IDENTITIES)]
    return f"train_{source_id:04d}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def row_for(filename: str, local_path: Path, root: Path) -> dict[str, str]:
    stem = Path(filename).stem
    source_id, camera = stem.split("_")
    identity = map_identity(int(source_id))
    camera_number = int(camera)
    is_evaluation = identity in (*TARGET_IDENTITIES, *DISTRACTOR_IDENTITIES)
    if is_evaluation and camera_number >= 4:
        split = "test"
        subset = f"query_{camera}"
    elif is_evaluation:
        split = "train"
        subset = f"gallery_{camera}"
    else:
        split = "train"
        subset = "train_0"
    relative = local_path.resolve().relative_to(root.resolve()).as_posix()
    return {
        "dataset": "Market1501-attributes",
        "sourceRepo": REPO_ID,
        "sourcePath": filename,
        "localPath": relative,
        "identityGroupId": identity,
        "sourceIdentityId": source_id,
        "sequenceId": f"camera_{camera}",
        "cameraId": camera,
        "split": split,
        "subset": subset,
        "frameName": Path(filename).name,
        "license": "CC-BY-4.0",
        "benchmarkRole": "query"
        if split == "test"
        else "gallery"
        if subset.startswith("gallery")
        else "train",
        "sha256": sha256(local_path),
    }


def fetch_one(filename: str, root: Path) -> dict[str, str]:
    local_path = root / filename
    if local_path.is_file():
        return row_for(filename, local_path, root)
    error: Exception | None = None
    for attempt in range(5):
        try:
            path = Path(
                hf_hub_download(
                    repo_id=REPO_ID,
                    filename=filename,
                    repo_type="dataset",
                    local_dir=root,
                )
            )
            return row_for(filename, path, root)
        except Exception as current:
            error = current
            if attempt < 4:
                time.sleep(min(60.0, 2.0**attempt * 5.0))
    if error is None:
        raise RuntimeError(filename)
    raise error


def write_rows(rows: list[dict[str, str]], output: Path) -> None:
    rows.sort(key=lambda row: str(row["sourcePath"]))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def selected_files(max_source_id: int) -> list[str]:
    return [
        filename
        for filename in HfApi().list_repo_files(REPO_ID, repo_type="dataset")
        if filename.startswith("data/")
        and filename.lower().endswith(".jpg")
        and int(Path(filename).stem.split("_")[0]) <= max_source_id
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-source-id", type=int, default=9999)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    files = selected_files(args.max_source_id)
    rows: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(fetch_one, filename, args.root): filename for filename in files}
        for number, future in enumerate(as_completed(futures), 1):
            filename = futures[future]
            try:
                rows.append(future.result())
            except Exception as error:
                print(f"failed {filename} {type(error).__name__}")
            if number % 50 == 0 or number == len(files):
                write_rows(rows, args.output)
                print(f"processed {number}/{len(files)} verified={len(rows)}")
    write_rows(rows, args.output)
    print(json.dumps({"selected": len(files), "verified": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
