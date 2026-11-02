from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

PETA_ATTRIBUTES = (
    "hat",
    "muffler",
    "no_headwear",
    "sunglasses",
    "long_hair",
    "upper_casual",
    "upper_formal",
    "upper_jacket",
    "upper_logo",
    "upper_plaid",
    "upper_short_sleeve",
    "upper_thin_stripes",
    "upper_tshirt",
    "upper_other",
    "upper_vneck",
    "lower_casual",
    "lower_formal",
    "lower_jeans",
    "lower_shorts",
    "lower_short_skirt",
    "lower_trousers",
    "shoes_leather",
    "shoes_sandals",
    "shoes_other",
    "shoes_sneakers",
    "backpack",
    "attachment_other",
    "messenger_bag",
    "no_attachment",
    "plastic_bags",
    "age_under_30",
    "age_30_45",
    "age_45_60",
    "age_over_60",
    "male",
)

PETA_PROMPTS = (
    "A pedestrian wearing a hat",
    "A pedestrian wearing a muffler",
    "A pedestrian with no headwear",
    "A pedestrian wearing sunglasses",
    "A pedestrian with long hair",
    "A pedestrian in casual upper wear",
    "A pedestrian in formal upper wear",
    "A pedestrian in a jacket",
    "A pedestrian in upper wear with a logo",
    "A pedestrian in plaid upper wear",
    "A pedestrian in a short-sleeved top",
    "A pedestrian in upper wear with thin stripes",
    "A pedestrian in a t-shirt",
    "A pedestrian in other upper wear",
    "A pedestrian in upper wear with a V-neck",
    "A pedestrian in casual lower wear",
    "A pedestrian in formal lower wear",
    "A pedestrian in jeans",
    "A pedestrian in shorts",
    "A pedestrian in a short skirt",
    "A pedestrian in trousers",
    "A pedestrian in leather shoes",
    "A pedestrian in sandals",
    "A pedestrian in other types of shoes",
    "A pedestrian in sneakers",
    "A pedestrian with a backpack",
    "A pedestrian with other types of attachments",
    "A pedestrian with a messenger bag",
    "A pedestrian with no attachments",
    "A pedestrian with plastic bags",
    "A pedestrian under the age of 30",
    "A pedestrian between the ages of 30 and 45",
    "A pedestrian between the ages of 45 and 60",
    "A pedestrian over the age of 60",
    "A male pedestrian",
)

PA100K_ATTRIBUTES = (
    "female",
    "age_over_60",
    "age_18_60",
    "age_under_18",
    "front",
    "side",
    "back",
    "hat",
    "glasses",
    "hand_bag",
    "shoulder_bag",
    "backpack",
    "hold_objects_front",
    "short_sleeve",
    "long_sleeve",
    "upper_stride",
    "upper_logo",
    "upper_plaid",
    "upper_splice",
    "lower_stripe",
    "lower_pattern",
    "long_coat",
    "trousers",
    "shorts",
    "skirt_dress",
    "boots",
)

PA100K_PROMPTS = (
    "A female pedestrian",
    "A pedestrian over the age of 60",
    "A pedestrian between the ages of 18 and 60",
    "A pedestrian under the age of 18",
    "A pedestrian seen from the front",
    "A pedestrian seen from the side",
    "A pedestrian seen from the back",
    "A pedestrian wearing a hat",
    "A pedestrian wearing glasses",
    "A pedestrian with a handbag",
    "A pedestrian with a shoulder bag",
    "A pedestrian with a backpack",
    "A pedestrian holding objects in front",
    "A pedestrian in short-sleeved upper wear",
    "A pedestrian in long-sleeved upper wear",
    "A pedestrian in stride upper wear",
    "A pedestrian in upper wear with a logo",
    "A pedestrian in plaid upper wear",
    "A pedestrian in splice upper wear",
    "A pedestrian in striped lower wear",
    "A pedestrian in patterned lower wear",
    "A pedestrian in a long coat",
    "A pedestrian in trousers",
    "A pedestrian in shorts",
    "A pedestrian in skirts and dresses",
    "A pedestrian wearing boots",
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openpar-root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--pretrained-vit", type=Path, required=True)
    parser.add_argument("--dataset", choices=("PETA", "PA100k"), required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    return parser.parse_args(argv)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    labels, prompts = _taxonomy(args.dataset)
    image_paths = sorted(
        path
        for path in args.image_root.rglob("*")
        if path.suffix.lower() in {".jpg", ".jpeg", ".png"}
    )
    if not image_paths:
        raise ValueError("image root contains no supported images")

    sys.path.insert(0, str(args.openpar_root))
    sys.argv = [
        "run_promptpar_gpu.py",
        args.dataset,
        "--checkpoint",
        "--dir",
        str(args.checkpoint),
        "--use_div",
        "--use_vismask",
        "--vis_prompt",
        "50",
        "--use_GL",
        "--use_textprompt",
        "--use_mm_former",
    ]

    import torch
    from clip.model import build_model
    from models.base_block import TransformerClassifier
    from PIL import Image
    from torch.utils.data import DataLoader, Dataset
    from torchvision import transforms

    class ImageDataset(Dataset[tuple[Any, str]]):
        def __len__(self) -> int:
            return len(image_paths)

        def __getitem__(self, index: int) -> tuple[Any, str]:
            path = image_paths[index]
            with Image.open(path) as source:
                image = source.convert("RGB")
            transform = transforms.Compose(
                (
                    transforms.Resize((224, 224)),
                    transforms.ToTensor(),
                    transforms.Normalize(mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5)),
                )
            )
            return transform(image), str(path)

    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    clip_model = build_model(checkpoint["ViT_model"])
    model = TransformerClassifier(
        clip_model,
        len(prompts),
        prompts,
        pretrain_path=str(args.pretrained_vit),
    )
    state_dict = {
        key.replace("vis_embed.", "visual_embed."): value
        for key, value in checkpoint["model_state_dict"].items()
    }
    load_result = model.load_state_dict(state_dict, strict=False)
    disallowed_unexpected = [
        key for key in load_result.unexpected_keys if not key.startswith("vit.")
    ]
    if load_result.missing_keys or disallowed_unexpected:
        raise RuntimeError(
            "checkpoint integrity failure: "
            f"missing={load_result.missing_keys}, unexpected={disallowed_unexpected}"
        )

    device = torch.device("cuda")
    model = model.to(device).eval()
    clip_model = clip_model.to(device).eval()
    loader = DataLoader(
        ImageDataset(),
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=True,
    )

    rows: list[dict[str, object]] = []
    with torch.inference_mode():
        for images, paths in loader:
            logits, _ = model(images.to(device, non_blocking=True), clip_model=clip_model)
            probabilities = torch.sigmoid(logits).cpu().tolist()
            for image_path, values in zip(paths, probabilities, strict=True):
                rows.append(
                    {
                        "imagePath": image_path,
                        "probabilities": dict(zip(labels, values, strict=True)),
                    }
                )

    payload = {
        "schemaVersion": "promptpar-frame-probabilities-v1",
        "dataset": args.dataset,
        "checkpoint": str(args.checkpoint),
        "checkpointSha256": sha256_file(args.checkpoint),
        "normalizedInput": True,
        "imageCount": len(rows),
        "loadIntegrity": {
            "missingKeys": [],
            "disallowedUnexpectedKeys": [],
            "ignoredPretrainedVitKeyCount": len(load_result.unexpected_keys),
        },
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0


def _taxonomy(dataset: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if dataset == "PETA":
        return PETA_ATTRIBUTES, PETA_PROMPTS
    if dataset == "PA100k":
        return PA100K_ATTRIBUTES, PA100K_PROMPTS
    raise ValueError(f"unsupported dataset: {dataset}")


if __name__ == "__main__":
    raise SystemExit(main())
