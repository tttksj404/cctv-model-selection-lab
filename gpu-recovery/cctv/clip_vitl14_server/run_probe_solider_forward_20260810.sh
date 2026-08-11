#!/usr/bin/env bash
set +e
cd <redacted-local-path>
export QWEN_ENABLE_LEGACY_MMCV_RUNNER_COMPAT=1
export CUDA_VISIBLE_DEVICES=0
conda run --no-capture-output -n qwen3vl python probe_solider_forward_20260810.py > <redacted-temp-path> 2>&1
status=$?
tail -120 <redacted-temp-path>
echo "probe_status=$status"
exit 0
