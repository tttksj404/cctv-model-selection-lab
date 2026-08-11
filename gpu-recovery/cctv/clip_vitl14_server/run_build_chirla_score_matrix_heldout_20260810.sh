#!/usr/bin/env bash
set +e
cd <redacted-local-path>
export QWEN_ENABLE_LEGACY_MMCV_RUNNER_COMPAT=1
export CUDA_VISIBLE_DEVICES=0
conda run --no-capture-output -n qwen3vl python build_chirla_feature_scores_heldout_20260810.py \
  --root experiments/data/chirla \
  --manifest experiments/data/chirla/chirla_solider_eval_20260810.jsonl \
  --output experiments/results/chirla_identity_heldout_score_matrices_20260810.npz \
  --device cuda \
  --batch-size 32 \
  --solider-checkpoint experiments/models/solider_reid/swin_base_msmt17.pth \
  --solider-root experiments/solider_reid_runtime_v3/SOLIDER-REID-runtime-8c08e1c \
  > <redacted-temp-path> 2>&1
status=$?
tail -180 <redacted-temp-path>
echo "score_matrix_status=$status"
exit 0
