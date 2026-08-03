from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypedDict

import numpy as np
import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModel, AutoProcessor, CLIPModel, CLIPProcessor

if __package__:
    from scripts.benchmark_chirla_support import (
        _family,
        _file_sha256,
        _install_mmcv_runner_compat,
        _install_torch_six_compat,
        _require_local_checkpoint,
        _require_matching_sha256,
        _resolve_model_root,
    )
    from scripts.reid_metrics import (
        IdentityRetrievalMetrics as Metrics,
    )
    from scripts.reid_metrics import (
        compute_identity_retrieval_metrics as _metrics,
    )
else:
    from benchmark_chirla_support import (
        _family,
        _file_sha256,
        _install_mmcv_runner_compat,
        _install_torch_six_compat,
        _require_local_checkpoint,
        _require_matching_sha256,
        _resolve_model_root,
    )
    from reid_metrics import (
        IdentityRetrievalMetrics as Metrics,
    )
    from reid_metrics import (
        compute_identity_retrieval_metrics as _metrics,
    )

MODEL_CHECKPOINTS = {
    "clip-vit-b32": "openai/clip-vit-base-patch32",
    "clip-vit-l14": "openai/clip-vit-large-patch14",
    "siglip2-base": "google/siglip2-base-patch16-224",
    "dinov2-base": "facebook/dinov2-base",
    "osnet-x1-0": "osnet_x1_0",
    "fastreid-sbs-r101-ibn": "https://github.com/JDAI-CV/fast-reid/releases/download/v0.1.1/market_sbs_R101-ibn.pth",
    "fastreid-agw-r101-ibn": "https://github.com/JDAI-CV/fast-reid/releases/download/v0.1.1/market_agw_R101-ibn.pth",
    "fastreid-bot-r101-ibn": "https://github.com/JDAI-CV/fast-reid/releases/download/v0.1.1/market_bot_R101-ibn.pth",
    "solider-reid-swin-base-msmt17": "models/solider_reid/swin_base_msmt17.pth",
}
FASTREID_CONFIGS = {
    "fastreid-sbs-r101-ibn": "configs/Market1501/sbs_R101-ibn.yml",
    "fastreid-agw-r101-ibn": "configs/Market1501/AGW_R101-ibn.yml",
    "fastreid-bot-r101-ibn": "configs/Market1501/AGW_R101-ibn.yml",
}
GalleryAggregation = Literal["mean", "max", "topk-mean"]
EvaluationProtocol = Literal["gallery-query", "strict-cross-camera-sequence"]


@dataclass(frozen=True, slots=True)
class Record:
    path: Path
    identity: str
    role: str
    camera: str
    sequence: str
    sha256: str


class Result(TypedDict):
    schema_version: str
    model: str
    checkpoint: str
    device: str
    tta: str
    dataset: str
    dataset_status: str
    manifest_sha256: str
    counts: dict[str, int]
    split_contract: dict[str, object]
    metric_semantics: dict[str, str]
    metrics: Metrics
    by_camera: dict[str, Metrics]
    by_sequence: dict[str, Metrics]
    query_rankings: list[dict[str, object]]


def _text(row: dict[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"manifest field {key!r} must be non-empty text")
    return value


def _load_records(root: Path, manifest: Path) -> list[Record]:
    records: list[Record] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row: object = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError("each manifest line must be a JSON object")
        relative_path = Path(_text(row, "localPath"))
        path = root / relative_path
        if not path.is_file():
            raise FileNotFoundError(path)
        expected_sha256 = _require_matching_sha256(
            path,
            _text(row, "sha256"),
            relative_path.as_posix(),
        )
        records.append(
            Record(
                path=path,
                identity=_text(row, "identityGroupId"),
                role=_text(row, "benchmarkRole"),
                camera=_text(row, "cameraId"),
                sequence=_text(row, "sequenceId"),
                sha256=expected_sha256,
            )
        )
    return records
def _device(name: str) -> torch.device:
    if name == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("--device cuda was requested but CUDA is unavailable")
    return torch.device(name)


class ImageEncoder:
    def __init__(
        self,
        model_name: str,
        device: torch.device,
        checkpoint_override: str | None = None,
        fastreid_root: Path | None = None,
        solider_root: Path | None = None,
        tta: str = "none",
    ) -> None:
        checkpoint = checkpoint_override or MODEL_CHECKPOINTS[model_name]
        self.model_name = model_name
        self.device = device
        self.family = _family(model_name)
        self._checkpoint = checkpoint
        self.tta = tta
        if self.family == "clip":
            self.processor = CLIPProcessor.from_pretrained(checkpoint)
            self.model = CLIPModel.from_pretrained(checkpoint).to(device).eval()
        elif self.family == "siglip2":
            self.processor = AutoProcessor.from_pretrained(checkpoint)
            self.model = AutoModel.from_pretrained(checkpoint).to(device).eval()
        elif self.family == "reid":
            import torchreid
            from torchvision.transforms import Compose, Normalize, Resize, ToTensor

            self.processor = Compose(
                [
                    Resize((256, 128)),
                    ToTensor(),
                    Normalize(
                        mean=[0.485, 0.456, 0.406],
                        std=[0.229, 0.224, 0.225],
                    ),
                ]
            )
            self.model = torchreid.models.build_model(
                name=checkpoint,
                num_classes=1,
                pretrained=True,
            ).to(device).eval()
        elif self.family == "fastreid":
            root = fastreid_root or (
                Path(os.environ["FASTREID_ROOT"])
                if os.environ.get("FASTREID_ROOT")
                else None
            )
            if root is None:
                raise RuntimeError(
                    "FastReID requires --fastreid-root or FASTREID_ROOT pointing to "
                    "a checked-out fast-reid repository"
                )
            root = _resolve_model_root(root, "fastreid")
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from fastreid.config import get_cfg
            from fastreid.engine import DefaultPredictor

            weights = _require_local_checkpoint(checkpoint, "FastReID")
            config_path = root / FASTREID_CONFIGS[model_name]
            if not config_path.is_file():
                raise FileNotFoundError(f"FastReID config not found: {config_path}")
            cfg = get_cfg()
            cfg.merge_from_file(str(config_path))
            cfg.MODEL.WEIGHTS = str(weights.resolve())
            cfg.MODEL.DEVICE = str(device)
            self.processor = None
            self.model = DefaultPredictor(cfg)
        elif self.family == "solider":
            root = solider_root or (
                Path(os.environ["SOLIDER_REID_ROOT"])
                if os.environ.get("SOLIDER_REID_ROOT")
                else None
            )
            if root is None:
                raise RuntimeError(
                    "SOLIDER-ReID requires --solider-root or SOLIDER_REID_ROOT "
                    "pointing to a checked-out SOLIDER-REID repository"
                )
            root = _resolve_model_root(root, "model")
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from torchvision.transforms import Compose, Normalize, Resize, ToTensor

            _install_torch_six_compat()
            _install_mmcv_runner_compat()
            from config import cfg as solider_cfg
            from model import make_model

            config_path = root / "configs" / "msmt17" / "swin_base.yml"
            if not config_path.is_file():
                raise FileNotFoundError(f"SOLIDER-ReID config not found: {config_path}")
            cfg = solider_cfg.clone()
            cfg.merge_from_file(str(config_path))
            cfg.MODEL.PRETRAIN_PATH = ""
            cfg.MODEL.PRETRAIN_CHOICE = "finetune"
            cfg.TEST.NECK_FEAT = "before"
            cfg.freeze()
            weights = _require_local_checkpoint(checkpoint, "SOLIDER-ReID")
            self.processor = Compose(
                [
                    Resize(tuple(cfg.INPUT.SIZE_TEST)),
                    ToTensor(),
                    Normalize(
                        mean=list(cfg.INPUT.PIXEL_MEAN),
                        std=list(cfg.INPUT.PIXEL_STD),
                    ),
                ]
            )
            self.model = make_model(
                cfg,
                num_class=1,
                camera_num=0,
                view_num=0,
                semantic_weight=0.2,
            )
            self.model.load_param(str(weights))
            self.model = self.model.to(device).eval()
        else:
            self.processor = AutoImageProcessor.from_pretrained(checkpoint)
            self.model = AutoModel.from_pretrained(checkpoint).to(device).eval()

    @property
    def checkpoint(self) -> str:
        return self._checkpoint

    def _images(self, records: Sequence[Record]) -> list[Image.Image]:
        images: list[Image.Image] = []
        for record in records:
            with Image.open(record.path) as image:
                images.append(image.convert("RGB"))
        return images

    def encode(self, records: Sequence[Record], batch_size: int) -> np.ndarray:
        chunks: list[np.ndarray] = []
        with torch.inference_mode():
            for start in range(0, len(records), batch_size):
                images = self._images(records[start : start + batch_size])
                if self.family in {"reid", "solider"}:
                    inputs = torch.stack([self.processor(image) for image in images]).to(
                        self.device
                    )
                    features = self.model(inputs)
                    if self.family == "solider":
                        if not isinstance(features, tuple) or not isinstance(
                            features[0], torch.Tensor
                        ):
                            raise TypeError("SOLIDER-ReID did not return feature tensor")
                        features = features[0]
                        if self.tta == "hflip":
                            flipped = self.model(torch.flip(inputs, dims=(3,)))
                            if not isinstance(flipped, tuple) or not isinstance(
                                flipped[0], torch.Tensor
                            ):
                                raise TypeError(
                                    "SOLIDER-ReID flipped inference did not return feature tensor"
                                )
                            features = torch.nn.functional.normalize(
                                features, dim=-1
                            ) + torch.nn.functional.normalize(flipped[0], dim=-1)
                elif self.family == "fastreid":
                    arrays = [
                        np.asarray(image.resize((128, 384)), dtype=np.uint8)[:, :, ::-1]
                        for image in images
                    ]
                    inputs = torch.from_numpy(np.stack(arrays)).permute(0, 3, 1, 2).float()
                    features = self.model(inputs)
                    if self.tta == "hflip":
                        flipped = [np.ascontiguousarray(np.flip(array, axis=1)) for array in arrays]
                        flipped_inputs = (
                            torch.from_numpy(np.stack(flipped))
                            .permute(0, 3, 1, 2)
                            .float()
                        )
                        flipped_features = self.model(flipped_inputs)
                        features = torch.nn.functional.normalize(
                            features, dim=-1
                        ) + torch.nn.functional.normalize(flipped_features, dim=-1)
                else:
                    inputs = self.processor(images=images, return_tensors="pt")
                    inputs = {key: value.to(self.device) for key, value in inputs.items()}
                if self.family == "clip":
                    features = self.model.get_image_features(**inputs)
                    if not isinstance(features, torch.Tensor):
                        vision_outputs = self.model.vision_model(**inputs)
                        features = self.model.visual_projection(vision_outputs.pooler_output)
                elif self.family == "siglip2":
                    vision_outputs = self.model.vision_model(
                        pixel_values=inputs["pixel_values"]
                    )
                    features = vision_outputs.pooler_output
                    projection = getattr(self.model, "visual_projection", None)
                    if projection is not None:
                        features = projection(features)
                elif self.family == "generic":
                    outputs = self.model(**inputs)
                    features = getattr(outputs, "pooler_output", None)
                    if features is None:
                        features = outputs.last_hidden_state[:, 0]
                if not isinstance(features, torch.Tensor):
                    raise TypeError(f"{self.model_name} did not return tensor image features")
                normalized = torch.nn.functional.normalize(features, dim=-1)
                chunks.append(normalized.float().cpu().numpy())
                for image in images:
                    image.close()
        return np.concatenate(chunks, axis=0)


def _group_metrics(
    scores: np.ndarray,
    queries: Sequence[Record],
    gallery_identities: Sequence[str],
    attribute: Literal["camera", "sequence"],
) -> dict[str, Metrics]:
    groups: dict[str, list[int]] = defaultdict(list)
    for index, record in enumerate(queries):
        groups[getattr(record, attribute)].append(index)
    return {
        group: _metrics(
            scores[indices],
            [queries[index].identity for index in indices],
            gallery_identities,
            bootstrap_seed=20260724 + index,
        )
        for index, (group, indices) in enumerate(sorted(groups.items()))
    }


def _aggregate_identity_scores(
    query_features: np.ndarray,
    gallery_features: np.ndarray,
    queries: Sequence[Record],
    gallery: Sequence[Record],
    identities: Sequence[str],
    gallery_indices: dict[str, list[int]],
    gallery_aggregation: GalleryAggregation,
    gallery_topk: int,
    protocol: EvaluationProtocol,
) -> np.ndarray:
    scores = np.full(
        (len(queries), len(identities)),
        fill_value=-np.inf,
        dtype=np.float32,
    )
    for query_index, query in enumerate(queries):
        for identity_index, identity in enumerate(identities):
            candidate_indices = gallery_indices[identity]
            if protocol == "strict-cross-camera-sequence":
                candidate_indices = [
                    index
                    for index in candidate_indices
                    if gallery[index].camera != query.camera
                    and gallery[index].sequence != query.sequence
                ]
            if not candidate_indices:
                continue
            candidate_features = gallery_features[candidate_indices]
            if gallery_aggregation == "mean":
                vector = candidate_features.mean(axis=0)
                vector /= np.linalg.norm(vector)
                scores[query_index, identity_index] = query_features[query_index] @ vector
                continue
            identity_scores = query_features[query_index] @ candidate_features.T
            if gallery_aggregation == "max":
                scores[query_index, identity_index] = identity_scores.max()
                continue
            topk = min(gallery_topk, identity_scores.shape[0])
            scores[query_index, identity_index] = np.sort(identity_scores)[-topk:].mean()
    return scores


def _query_rankings(
    scores: np.ndarray,
    queries: Sequence[Record],
    identities: Sequence[str],
) -> list[dict[str, object]]:
    identity_array = np.asarray(identities)
    rankings: list[dict[str, object]] = []
    for index, query in enumerate(queries):
        finite = np.isfinite(scores[index])
        order = np.argsort(-scores[index], kind="stable")
        order = order[finite[order]]
        target_positions = np.flatnonzero(identity_array[order] == query.identity)
        if len(target_positions) == 0:
            raise ValueError(
                f"query identity {query.identity!r} has no eligible gallery under protocol"
            )
        top_identity = str(identity_array[order[0]])
        top_score = float(scores[index, order[0]])
        second_score = float(scores[index, order[1]]) if len(order) > 1 else None
        rankings.append(
            {
                "query_path": str(query.path),
                "query_identity": query.identity,
                "query_camera": query.camera,
                "query_sequence": query.sequence,
                "eligible_gallery_identities": int(finite.sum()),
                "rank": int(target_positions[0]) + 1,
                "top1_identity": top_identity,
                "top1_score": top_score,
                "target_score": float(
                    scores[index, identities.index(query.identity)]
                ),
                "top1_margin": (
                    top_score - second_score if second_score is not None else None
                ),
            }
        )
    return rankings


def evaluate(
    records: Sequence[Record],
    encoder: ImageEncoder,
    batch_size: int,
    gallery_aggregation: GalleryAggregation,
    gallery_topk: int,
    dataset_name: str = "CHIRLA",
    dataset_status: str = "public-proxy-not-project-CCTV-review",
    protocol: EvaluationProtocol = "gallery-query",
) -> Result:
    gallery = [record for record in records if record.role == "gallery"]
    queries = [record for record in records if record.role == "query"]
    gallery_by_identity: dict[str, list[Record]] = defaultdict(list)
    for record in gallery:
        gallery_by_identity[record.identity].append(record)
    query_identities = {record.identity for record in queries}
    identities = sorted(query_identities & set(gallery_by_identity))
    if len(identities) < 10:
        raise ValueError(f"formal gate requires at least 10 identities, found {len(identities)}")
    gallery = [record for identity in identities for record in gallery_by_identity[identity]]
    queries = [record for record in queries if record.identity in identities]
    if protocol == "strict-cross-camera-sequence":
        queries = [
            query
            for query in queries
            if any(
                record.identity == query.identity
                and record.camera != query.camera
                and record.sequence != query.sequence
                for record in gallery
            )
        ]
        if not queries:
            raise ValueError(
                "strict cross-camera/sequence protocol has no eligible queries"
            )
    gallery_features = encoder.encode(gallery, batch_size)
    query_features = encoder.encode(queries, batch_size)
    gallery_indices = {
        identity: [
            index for index, record in enumerate(gallery) if record.identity == identity
        ]
        for identity in identities
    }
    scores = _aggregate_identity_scores(
        query_features,
        gallery_features,
        queries,
        gallery,
        identities,
        gallery_indices,
        gallery_aggregation,
        gallery_topk,
        protocol,
    )
    query_identity_list = [record.identity for record in queries]
    metrics = _metrics(scores, query_identity_list, identities)
    query_sequences = {record.sequence for record in queries}
    gallery_sequences = {record.sequence for record in gallery}
    return {
        "schema_version": "cctv-chirla-identity-reid-v2",
        "model": encoder.model_name,
        "checkpoint": encoder.checkpoint,
        "device": str(encoder.device),
        "tta": encoder.tta,
        "dataset": dataset_name,
        "dataset_status": dataset_status,
        "manifest_sha256": "",
        "counts": {
            "all_manifest_records": len(records),
            "gallery_records": len(gallery),
            "query_records": len(queries),
            "gallery_identities": len(identities),
            "query_identities": len(query_identities),
            "query_gallery_identity_intersection": len(identities),
        },
        "split_contract": {
            "gallery_role": "gallery",
            "query_role": "query",
            "protocol": protocol,
            "excludes_same_camera_gallery": (
                protocol == "strict-cross-camera-sequence"
            ),
            "excludes_same_sequence_gallery": (
                protocol == "strict-cross-camera-sequence"
            ),
            "identity_aggregation": gallery_aggregation,
            "gallery_topk": gallery_topk,
            "query_gallery_sequence_overlap": sorted(query_sequences & gallery_sequences),
            "query_gallery_camera_overlap": sorted(
                {record.camera for record in queries} & {record.camera for record in gallery}
            ),
        },
        "metric_semantics": {
            "identity_mrr": (
                "mean reciprocal rank after gallery crops are aggregated to one score "
                "per identity; this is not standard image-level ReID mAP"
            )
        },
        "metrics": metrics,
        "by_camera": _group_metrics(scores, queries, identities, "camera"),
        "by_sequence": _group_metrics(scores, queries, identities, "sequence"),
        "query_rankings": _query_rankings(scores, queries, identities),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate manifest-based identity retrieval")
    parser.add_argument("--root", type=Path, default=Path("experiments/data/chirla"))
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--model", choices=sorted(MODEL_CHECKPOINTS), required=True)
    parser.add_argument("--checkpoint", type=str, default=None)
    parser.add_argument("--fastreid-root", type=Path, default=None)
    parser.add_argument("--solider-root", type=Path, default=None)
    parser.add_argument("--tta", choices=["none", "hflip"], default="none")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    parser.add_argument("--dataset-name", default="CHIRLA")
    parser.add_argument(
        "--dataset-status",
        default="public-proxy-not-project-CCTV-review",
    )
    parser.add_argument(
        "--gallery-aggregation",
        choices=["mean", "max", "topk-mean"],
        default="mean",
        help="how gallery images are scored for each identity",
    )
    parser.add_argument(
        "--gallery-topk",
        type=int,
        default=5,
        help="number of gallery images for topk-mean aggregation",
    )
    parser.add_argument(
        "--protocol",
        choices=["gallery-query", "strict-cross-camera-sequence"],
        default="gallery-query",
        help="gallery/query scoring contract",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.batch_size < 1:
        raise ValueError("--batch-size must be positive")
    if args.gallery_topk < 1:
        raise ValueError("--gallery-topk must be positive")
    manifest = args.manifest or args.root / "chirla_identity_manifest.jsonl"
    records = _load_records(args.root, manifest)
    encoder = ImageEncoder(
        args.model,
        _device(args.device),
        checkpoint_override=args.checkpoint,
        fastreid_root=args.fastreid_root,
        solider_root=args.solider_root,
        tta=args.tta,
    )
    result = evaluate(
        records,
        encoder,
        args.batch_size,
        args.gallery_aggregation,
        args.gallery_topk,
        args.dataset_name,
        args.dataset_status,
        args.protocol,
    )
    result["manifest_sha256"] = _file_sha256(manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result["metrics"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
