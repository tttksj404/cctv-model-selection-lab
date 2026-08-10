#!/usr/bin/env bash
set -euo pipefail

workspace="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$workspace"

archive="data/prid2011/source/prid_2011.zip"
download_status="results/prid_download.status"
expected_bytes=1064626547
python_bin=".venv-solider/bin/python"
manifest="data/prid2011/prid2011_track_manifest.jsonl"
extract_root="data/prid2011/extracted"
pipeline_log="results/prid_gpu_pipeline.log"

mkdir -p results "$extract_root"
exec > >(tee -a "$pipeline_log") 2>&1

echo "stage=wait_download"
for _ in $(seq 1 360); do
  current_bytes="$(stat -c%s "$archive" 2>/dev/null || echo 0)"
  current_status=""
  if [[ -f "$download_status" ]]; then
    current_status="$(tr -d '\r\n ' < "$download_status")"
  fi
  if [[ "$current_bytes" == "$expected_bytes" && "$current_status" == "0" ]]; then
    break
  fi
  sleep 5
done

actual_bytes="$(stat -c%s "$archive")"
if [[ "$actual_bytes" != "$expected_bytes" ]]; then
  echo "archive_size_mismatch expected=$expected_bytes actual=$actual_bytes"
  exit 10
fi
if [[ "$(tr -d '\r\n ' < "$download_status")" != "0" ]]; then
  echo "download_status_failed"
  exit 11
fi

echo "stage=verify_archive"
sha256sum "$archive" > results/prid2011_archive.sha256
"$python_bin" -m zipfile -t "$archive" > results/prid2011_archive_test.txt

echo "stage=extract"
if [[ ! -f "$extract_root/.complete" ]]; then
  "$python_bin" -m zipfile -e "$archive" "$extract_root"
  touch "$extract_root/.complete"
fi

echo "stage=build_manifest"
PYTHONPATH=. "$python_bin" scripts/build_prid2011_manifest.py \
  --extracted-root "$extract_root" \
  --output "$manifest" \
  --train-identities 80 \
  --validation-identities 20 \
  --shared-identities 200

data_root="$(
  "$python_bin" -c \
    'import json, pathlib; print(json.loads(pathlib.Path("data/prid2011/prid2011_track_manifest.summary.json").read_text())["dataRoot"])'
)"

run_model() {
  local gpu="$1"
  local name="$2"
  shift 2
  (
    set +e
    CUDA_VISIBLE_DEVICES="$gpu" PYTHONPATH=. "$python_bin" \
      scripts/benchmark_prid2011_tracks.py \
      --root "$data_root" \
      --manifest "$manifest" \
      --device cuda \
      --batch-size 64 \
      --tta hflip \
      --output "results/prid2011_${name}.json" \
      "$@" \
      > "results/prid2011_${name}.log" 2>&1
    status=$?
    echo "$status" > "results/prid2011_${name}.status"
    exit "$status"
  ) &
  model_pids+=("$!")
}

echo "stage=frozen_baseline"
model_pids=()
run_model 0 solider \
  --model solider-reid-swin-base-msmt17 \
  --checkpoint models/solider_reid/swin_base_msmt17.pth \
  --solider-root external/SOLIDER-REID
run_model 1 clip_l14 --model clip-vit-l14
run_model 2 siglip2_base --model siglip2-base
run_model 3 fastreid_sbs \
  --model fastreid-sbs-r101-ibn \
  --checkpoint models/market_sbs_R101-ibn.pth \
  --fastreid-root external/fast-reid

pipeline_status=0
for pid in "${model_pids[@]}"; do
  wait "$pid" || pipeline_status=1
done
echo "$pipeline_status" > results/prid2011_frozen_sweep.status
echo "stage=complete status=$pipeline_status"
exit "$pipeline_status"

