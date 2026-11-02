# Models and data used by these experiments

Experiments from `qwen3vl-backend/experiments` (2026-07-22 ~ 2026-08-11): notebooks, reports, results and
the small attribute/ReID heads trained here. Large public weights and raw CCTV data are not stored in git.

## Public pretrained weights (download again from the source)

| Local path (`models/`) | Source | File | Bytes | SHA-256 |
|---|---|---|---|---|
| `Qwen3-VL-2B-Instruct/` | HF `Qwen/Qwen3-VL-2B-Instruct` | `model.safetensors` | 4255140312 | `7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0` |
| `Florence-2-large/` | HF `microsoft/Florence-2-large` | `model.safetensors` | 1553563458 | `4f38ce741c6b71188fe2b3419a55e11917a8a7b321ae2e63c61da0191b0ebad7` |
| `Florence-2-large-ft/` | HF `microsoft/Florence-2-large-ft` | `model.safetensors` | 1540980506 | `8b4e610c952eef90a836c56cda0f398a672a3a6ca7b4d96b0e09a86dee42e2c3` |
| `solider_swin_base.pth` | SOLIDER Swin-B (see `gpu-recovery/cctv/clip_vitl14_server/scripts/download_solider_reid.py`) | `solider_swin_base.pth` | 1767962390 | `20c1105ac7b58f444092d9e3b589150e107a7320a34f321353276ff5c5a9f3d1` |

```bash
huggingface-cli download Qwen/Qwen3-VL-2B-Instruct --local-dir models/Qwen3-VL-2B-Instruct
huggingface-cli download microsoft/Florence-2-large --local-dir models/Florence-2-large
huggingface-cli download microsoft/Florence-2-large-ft --local-dir models/Florence-2-large-ft
```

## Trained heads (in git)

`models/heads/*.pt` and `results/**/*.pt` are the small heads trained in these experiments.

## Not in git

- Real CCTV footage and frames (`data/cctv_real`): contains real people, kept offline only.
  Extracted frames can be regenerated from the source videos.
- Public datasets (PA-100K, Market-1501, PRID2011, CHIRLA): download from their original sources.
- Image outputs of real footage (contact sheets, crops, `.npz` track embeddings) were left out of `results/`,
  and image outputs were stripped from notebooks other than the model-comparison bubble charts.
- `vendor/SOLIDER-PersonAttributeRecognition`: upstream third-party code.
