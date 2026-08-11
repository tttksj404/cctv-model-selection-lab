from __future__ import annotations

# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

import json
from pathlib import Path

import torch
from PIL import Image

from scripts.benchmark_chirla_reid import ImageEncoder


def shape(value: object) -> object:
    if isinstance(value, torch.Tensor):
        return {"type": "Tensor", "shape": list(value.shape), "dtype": str(value.dtype)}
    if isinstance(value, (list, tuple)):
        return {"type": type(value).__name__, "items": [shape(item) for item in value]}
    return {"type": type(value).__name__}


def main() -> None:
    root = Path("experiments/data/chirla")
    manifest = Path("experiments/data/chirla/chirla_solider_trainval_20260810.jsonl")
    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()][:2]
    device = torch.device("cuda:0")
    encoder = ImageEncoder(
        "solider-reid-swin-base-msmt17",
        device,
        checkpoint_override="experiments/models/solider_reid/swin_base_msmt17.pth",
        solider_root=Path("experiments/solider_reid_runtime_v3/SOLIDER-REID-runtime-8c08e1c"),
        tta="none",
    )
    model = encoder.model
    inputs = torch.stack([
        encoder.processor(Image.open(root / row["localPath"]).convert("RGB"))
        for row in rows
    ]).to(device)
    with torch.no_grad():
        model.eval()
        eval_output = model(inputs)
        model.train()
        train_output = model(inputs, label=torch.zeros(2, dtype=torch.long, device=device))
        base_output = model.base(inputs)
    print(json.dumps({
        "eval": shape(eval_output),
        "train": shape(train_output),
        "base": shape(base_output),
        "attributes": sorted(name for name in dir(model) if name in {"base", "bottleneck", "classifier", "b1", "b2", "bottleneck_1", "bottleneck_2"}),
        "modelTraining": model.training,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
