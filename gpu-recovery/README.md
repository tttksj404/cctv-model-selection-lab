# GPU recovery archive — CCTV

This directory contains the public-safe part of the CCTV experiments recovered from the GPU Jupyter workspace on 2026-08-11.

## Recovery verification

- 8,949 real files were downloaded locally (5.889 GiB).
- Every downloaded file was verified with its recorded size and SHA-256 hash.
- The verification summary is in `manifests/download_verification_summary.json`.

## Deliberately excluded

Raw CCTV video, person crops and frames, personally identifying images, private datasets, credentials, and internal absolute paths are not published here. The complete model inventory records 305.813 GiB of weights and remains outside this public archive; selected project checkpoints and runtime artifacts are included separately under `weights/` using Git LFS.

## TTS check

No TTS project source or TTS media was found in the GPU workspace inventory. No TTS files were invented or included in this CCTV repository.

## Contents

- `cctv/`: public-safe source code, configuration, experiment notes, logs, and selected metric figures.
- `manifests/`: recovery verification, model-size summary, and the public inclusion summary.
- `weights/`: selected SOLIDER, edge-detector, and promoted zone-policy artifacts; verify with `manifests/weight_artifacts_20260811.json`.
- `IMPLEMENTATION_READY.md`: how to continue the implementation and the reset safety gate.
