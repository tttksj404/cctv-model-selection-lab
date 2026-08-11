#!/usr/bin/env bash
set -euo pipefail

cd <redacted-local-path>
export QWEN_ENABLE_LEGACY_MMCV_RUNNER_COMPAT=1
export CUDA_VISIBLE_DEVICES=0

for tta in none hflip; do
  for aggregation in mean max topk-mean; do
    name="chirla_identity_heldout_solider_${tta}_${aggregation//-/_}_20260810"
    echo "START ${name}"
    conda run --no-capture-output -n qwen3vl python scripts/benchmark_chirla_reid.py \
      --root experiments/data/chirla \
      --manifest experiments/data/chirla/chirla_solider_eval_20260810.jsonl \
      --model solider-reid-swin-base-msmt17 \
      --checkpoint experiments/models/solider_reid/swin_base_msmt17.pth \
      --solider-root experiments/solider_reid_runtime_v3/SOLIDER-REID-runtime-8c08e1c \
      --tta "$tta" \
      --batch-size 32 \
      --device cuda \
      --gallery-aggregation "$aggregation" \
      --protocol strict-cross-camera-sequence \
      --output "experiments/results/${name}.json"
    echo "DONE ${name}"
  done
done
