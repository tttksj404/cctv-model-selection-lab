from __future__ import annotations

from pathlib import Path

import torch


path = Path("<redacted-local-path>")
payload = torch.load(path, map_location="cpu", weights_only=False)
print("type", type(payload).__name__)
if isinstance(payload, dict):
    print("keys", list(payload)[:20])
    for section_name in ("student", "teacher", "state_dict", "model"):
        state = payload.get(section_name)
        if not isinstance(state, dict):
            continue
        print("section", section_name, "count", len(state))
        for key, value in list(state.items())[:20]:
            shape = tuple(value.shape) if hasattr(value, "shape") else None
            print(key, shape)
