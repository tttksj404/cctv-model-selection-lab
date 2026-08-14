# GPU recovery archive: implementation-ready scope

This archive contains the code and experiment evidence needed to continue the CCTV AI work after the GPU workspace is reset. It is intentionally a reproducible **implementation archive**, not a public dump of personal CCTV data or model binaries.

## What is preserved in this GitHub archive

- CCTV model-selection source code under `gpu-recovery/cctv/`.
- Training, evaluation, orchestration, zone-policy, and Qwen backend notebooks and scripts.
- Configuration examples, tests, experiment logs, metric figures, and promotion-gate evidence.
- Recovery manifests that identify the files, model families, sizes, and verification results.
- Selected trained checkpoints and runtime artifacts under `weights/`, with SHA-256 values in `manifests/weight_artifacts_20260811.json`.
- A human-readable experiment, parameter, metric, and weight index in `manifests/experiment_artifacts_summary.md`.
- A recovery-completeness checklist in `manifests/recovery_completeness_20260814.md`.
- The server root snapshot, so the previous workspace layout can be recreated without guessing names.

## Verified recovery facts

| Item | Verified value |
| --- | ---: |
| Locally recovered CCTV files | 8,949 |
| Locally recovered CCTV payload | 5.889 GiB |
| Locally recovered files with size/hash verification | 8,949 |
| Public-safe files included in this archive | 1,171 |
| Model files preserved in the server inventory | 198 |
| Full server model inventory size (not all uploaded) | 305.813 GiB |
| Selected checkpoints/runtime artifacts uploaded | 2.371 GiB |

The raw recordings, person crops/frames, private datasets, credentials, and internal absolute paths are not committed to GitHub. The selected checkpoints in `weights/` are committed through Git LFS. The full 305.813 GiB model inventory is not fully uploaded; the inventory files are the source of truth for restoring the remaining base models from private storage or re-downloading them.

## Continue on another machine

```powershell
git clone https://github.com/tttksj404/cctv-model-selection-lab.git
Set-Location cctv-model-selection-lab
git checkout agent/gpu-cctv-recovery-20260811
git lfs pull

python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e .
```

Install the runtime dependencies listed by the selected worker/model subproject before running a notebook. Keep data, model, cache, and output roots outside Git:

```text
CCTV_DATA_ROOT=<private recording or dataset root>
CCTV_MODEL_ROOT=<private model/checkpoint root>
CCTV_OUTPUT_ROOT=<local experiment output root>
```

The source of truth for dataset membership is each experiment's manifest builder and validation script. Run the validator before training; do not infer identity labels from a directory name or from a copied frame.

## Restore order after a server reset

1. Clone this branch and verify the commit shown by `git rev-parse HEAD`.
2. Restore private recordings/datasets into `CCTV_DATA_ROOT`.
3. Run `git lfs pull` and restore or re-download the remaining model weights into `CCTV_MODEL_ROOT` using `manifests/model_inventory_20260811.json`.
4. Run the manifest validators in the relevant experiment directory.
5. Run the unit tests and a small smoke inference before a long training job.
6. Record the new data/model hashes and evaluation split in the experiment result directory.

## Reset safety gate

This document does not authorize deleting a server directory. A reset is safe only after the private data and the complete trained-weight inventory have an independent copy, the target directory has been resolved to the intended user workspace, and a read-back confirms that no system/shared directory is in scope. The GitHub archive contains selected checkpoints, but it is not a complete backup of the 305.813 GiB model inventory.
