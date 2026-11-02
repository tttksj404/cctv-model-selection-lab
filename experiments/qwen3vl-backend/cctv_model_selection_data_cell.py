import json
from pathlib import Path

import pandas as pd
from IPython.display import display

project_root = Path.cwd().parent if Path.cwd().name == "experiments" else Path.cwd()
results_root = project_root / "experiments" / "results"
model_config = [
    {
        "file": "clip-vit-l14.track-contract-rerun.json",
        "model": "CLIP ViT-L/14",
        "params_b": 0.427,
        "role": "teacher/reference",
    },
    {
        "file": "clip-vit-b32.track-contract-rerun.json",
        "model": "CLIP ViT-B/32",
        "params_b": 0.151,
        "role": "edge candidate",
    },
    {
        "file": "qwen3-vl-2b.track-contract-rerun.json",
        "model": "Qwen3-VL-2B",
        "params_b": 2.0,
        "role": "server VLM",
    },
    {
        "file": "siglip-base.track-contract-rerun.json",
        "model": "SigLIP base",
        "params_b": 0.203,
        "role": "retrieval candidate",
    },
    {
        "file": "blip-base.track-contract-rerun.json",
        "model": "BLIP base",
        "params_b": 0.385,
        "role": "caption candidate",
    },
]
rows = []
for config in model_config:
    payload = json.loads((results_root / config["file"]).read_text(encoding="utf-8"))
    summary = payload["summary"]
    if summary["status"] != "valid":
        raise ValueError(f"invalid result status: {config['file']}")
    rows.append(
        {
            "모델": config["model"],
            "역할": config["role"],
            "속성 proxy 정확도(%)": round(summary["attribute_accuracy"] * 100, 4),
            "구조화 출력 유효율(%)": round(summary["structured_valid_rate"] * 100, 4),
            "p95 지연(s)": round(summary["latency_s_p95"], 4),
            "track exact match(%)": round(summary["track_exact_match"] * 100, 4),
            "예시 수": summary["examples"],
            "그룹 수": summary["groups"],
            "파라미터(B)": config["params_b"],
        }
    )
dataframe = pd.DataFrame(rows)
display(dataframe)
