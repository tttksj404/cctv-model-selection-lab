#!/usr/bin/env bash
set +e
cd <redacted-local-path>
conda run --no-capture-output -n qwen3vl python analyze_score_fusion_heldout_20260810.py \
  --scores experiments/results/chirla_identity_heldout_score_matrices_20260810.npz \
  --metadata experiments/results/chirla_identity_heldout_score_matrices_20260810.json \
  --output experiments/results/chirla_identity_heldout_score_fusion_20260810.json
status=$?
echo "fusion_status=$status"
exit 0
