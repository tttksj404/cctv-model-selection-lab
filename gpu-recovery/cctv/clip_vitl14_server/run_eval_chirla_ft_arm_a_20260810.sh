#!/usr/bin/env bash
set +e
cd <redacted-local-path>
export QWEN_ENABLE_LEGACY_MMCV_RUNNER_COMPAT=1
export CUDA_VISIBLE_DEVICES=0
for tta in none hflip; do
  for aggregation in mean max topk-mean; do
    name=chirla_identity_heldout_ft_arm_a_${tta}_${aggregation}_20260810
    conda run --no-capture-output -n qwen3vl python scripts/benchmark_chirla_reid.py \
      --root experiments/data/chirla \
      --manifest experiments/data/chirla/chirla_solider_eval_20260810.jsonl \
      --model solider-reid-swin-base-msmt17 \
      --checkpoint experiments/results/chirla_solider_ft_arm_a_20260810.pth \
      --solider-root experiments/solider_reid_runtime_v3/SOLIDER-REID-runtime-8c08e1c \
      --protocol strict-cross-camera-sequence \
      --tta "$tta" \
      --gallery-aggregation "$aggregation" \
      --device cuda \
      --batch-size 64 \
      --output "experiments/results/${name}.json" \
      | tee "<redacted-temp-path>"
  done
done
exit 0
