#!/usr/bin/env bash
set -e
cd <redacted-local-path>
mkdir -p experiments/data/chirla
cp chirla_validation_tmp_20260810.jsonl experiments/data/chirla/chirla_solider_validation_20260810.jsonl
cp chirla_validation_summary_tmp_20260810.json experiments/data/chirla/chirla_validation_selection_manifest_20260810.json
sha256sum experiments/data/chirla/chirla_solider_validation_20260810.jsonl experiments/data/chirla/chirla_validation_selection_manifest_20260810.json
