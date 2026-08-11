#!/usr/bin/env bash
set +e
cd <redacted-local-path>
echo "pwd=$(pwd)"
ls -l chirla_validation_tmp_20260810.jsonl chirla_validation_summary_tmp_20260810.json
ls -ld experiments experiments/data experiments/data/chirla
mkdir -p experiments/data/chirla
echo "mkdir_status=$?"
cp chirla_validation_tmp_20260810.jsonl experiments/data/chirla/chirla_solider_validation_20260810.jsonl
echo "manifest_cp_status=$?"
cp chirla_validation_summary_tmp_20260810.json experiments/data/chirla/chirla_validation_selection_manifest_20260810.json
echo "summary_cp_status=$?"
sha256sum experiments/data/chirla/chirla_solider_validation_20260810.jsonl experiments/data/chirla/chirla_validation_selection_manifest_20260810.json
exit 0
