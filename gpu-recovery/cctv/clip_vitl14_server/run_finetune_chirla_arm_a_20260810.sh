#!/usr/bin/env bash
set +e
cd <redacted-local-path>
export QWEN_ENABLE_LEGACY_MMCV_RUNNER_COMPAT=1
export CUDA_VISIBLE_DEVICES=0
conda run --no-capture-output -n qwen3vl python finetune_chirla_solider_identity_heldout_20260810.py \
  --root experiments/data/chirla \
  --manifest experiments/data/chirla/chirla_solider_trainval_20260810.jsonl \
  --checkpoint experiments/models/solider_reid/swin_base_msmt17.pth \
  --expected-checkpoint-sha256 81555144f412d46182d9cc8a0a01334f470a3484ce2fede88af9a5779d2a05a7 \
  --solider-root experiments/solider_reid_runtime_v3/SOLIDER-REID-runtime-8c08e1c \
  --output-checkpoint experiments/results/chirla_solider_ft_arm_a_20260810.pth \
  --output experiments/results/chirla_solider_ft_arm_a_20260810.json \
  --epochs 8 \
  --steps-per-epoch 25 \
  --identities-per-batch 8 \
  --images-per-identity 4 \
  --backbone-lr 2e-6 \
  --head-lr 3e-4 \
  --arc-margin 0.20 \
  --arc-scale 32 \
  --triplet-weight 1.0 \
  --part-weight 0.20 \
  --teacher-weight 1.0 \
  --seed 20260810 > <redacted-temp-path> 2>&1
status=$?
tail -180 <redacted-temp-path>
echo "finetune_status=$status"
exit 0
