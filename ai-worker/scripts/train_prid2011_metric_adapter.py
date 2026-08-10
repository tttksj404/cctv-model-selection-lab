from __future__ import annotations

import argparse
import json
import math
import random
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol, TypedDict

import numpy as np
import torch
import torch.nn.functional as F
from torch import Tensor, nn

from scripts.prid2011_open_set_features import (
    FEATURE_NAMES,
    OpenSetBatch,
    build_training_episodes,
    decision_metrics,
    extract_open_set_batch,
    select_threshold,
)
from scripts.prid2011_open_set_models import (
    LinearProbabilityHead,
    ProbabilityModel,
    TanhProbabilityHead,
)
from scripts.prid2011_track_cache import load_track_cache
from scripts.prid2011_track_metrics import TrackEmbedding


class MetricAdapterError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AdapterConfig:
    name: str
    rank: int
    residual_scale: float
    epochs: int
    learning_rate: float
    arc_margin: float
    triplet_margin: float
    geometry_weight: float
    preserve_weight: float
    seed: int


class CandidateRow(TypedDict):
    name: str
    config: dict[str, int | float | str]
    threshold: float
    openSetHead: str
    validationFeasible: bool
    validationMetrics: dict[str, int | float]
    finalLoss: float | None


class VectorAdapter(Protocol):
    def transform(self, vectors: np.ndarray) -> np.ndarray: ...

    def state(self) -> dict[str, np.ndarray]: ...


class IdentityVectorAdapter:
    def transform(self, vectors: np.ndarray) -> np.ndarray:
        return _normalize_numpy(vectors)

    def state(self) -> dict[str, np.ndarray]:
        return {}


class ResidualMetricAdapter(nn.Module):
    def __init__(self, input_dim: int, rank: int, residual_scale: float) -> None:
        super().__init__()
        self.down = nn.Linear(input_dim, rank, bias=False)
        self.up = nn.Linear(rank, input_dim, bias=False)
        self.residual_scale = residual_scale
        nn.init.normal_(self.down.weight, std=1.0 / math.sqrt(input_dim))
        nn.init.zeros_(self.up.weight)

    def forward(self, values: Tensor) -> Tensor:
        source = F.normalize(values, dim=-1)
        delta = self.up(torch.tanh(self.down(source)))
        return F.normalize(source + self.residual_scale * delta, dim=-1)


class TorchVectorAdapter:
    def __init__(self, model: ResidualMetricAdapter, device: torch.device) -> None:
        self.model = model.eval()
        self.device = device

    def transform(self, vectors: np.ndarray) -> np.ndarray:
        with torch.inference_mode():
            tensor = torch.as_tensor(vectors, dtype=torch.float32, device=self.device)
            transformed = self.model(tensor).cpu().numpy()
        return np.asarray(transformed, dtype=np.float32)

    def state(self) -> dict[str, np.ndarray]:
        return {
            name: parameter.detach().cpu().numpy()
            for name, parameter in self.model.state_dict().items()
        }


class ArcFaceHead(nn.Module):
    def __init__(
        self,
        input_dim: int,
        class_count: int,
        scale: float = 30.0,
        margin: float = 0.35,
    ) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.empty(class_count, input_dim))
        nn.init.xavier_uniform_(self.weight)
        self.scale = scale
        self.margin = margin

    def forward(self, embeddings: Tensor, labels: Tensor) -> Tensor:
        cosine = F.linear(F.normalize(embeddings), F.normalize(self.weight))
        sine = torch.sqrt(torch.clamp(1.0 - cosine.square(), min=1e-7))
        phi = cosine * math.cos(self.margin) - sine * math.sin(self.margin)
        threshold = math.cos(math.pi - self.margin)
        phi = torch.where(
            cosine > threshold,
            phi,
            cosine - math.sin(math.pi - self.margin) * self.margin,
        )
        one_hot = F.one_hot(labels, num_classes=self.weight.shape[0]).to(cosine.dtype)
        return self.scale * (one_hot * phi + (1.0 - one_hot) * cosine)


def _normalize_numpy(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float32)
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    if np.any(norms <= 0):
        raise MetricAdapterError("track cache contains a zero-norm vector")
    return np.asarray(values / norms, dtype=np.float32)


def _supervised_contrastive_loss(
    embeddings: Tensor, labels: Tensor, temperature: float = 0.07
) -> Tensor:
    logits = embeddings @ embeddings.T / temperature
    diagonal = torch.eye(len(embeddings), device=embeddings.device, dtype=torch.bool)
    logits = logits.masked_fill(diagonal, -torch.inf)
    positive = labels[:, None].eq(labels[None, :]) & ~diagonal
    log_prob = logits - torch.logsumexp(logits, dim=1, keepdim=True)
    return -(
        log_prob.masked_fill(~positive, 0.0).sum(dim=1)
        / positive.sum(dim=1).clamp_min(1)
    ).mean()


def _batch_hard_triplet_loss(
    embeddings: Tensor, labels: Tensor, margin: float
) -> Tensor:
    distances = 1.0 - embeddings @ embeddings.T
    diagonal = torch.eye(len(embeddings), device=embeddings.device, dtype=torch.bool)
    positive = labels[:, None].eq(labels[None, :]) & ~diagonal
    negative = labels[:, None].ne(labels[None, :])
    hardest_positive = distances.masked_fill(~positive, -torch.inf).max(dim=1).values
    hardest_negative = distances.masked_fill(~negative, torch.inf).min(dim=1).values
    return F.softplus((hardest_positive - hardest_negative + margin) * 10.0).mean() / 10.0


def _train_arrays(
    tracks: Sequence[TrackEmbedding],
) -> tuple[np.ndarray, np.ndarray]:
    train_tracks = [track for track in tracks if track.split == "train"]
    by_identity: dict[str, list[TrackEmbedding]] = {}
    for track in train_tracks:
        by_identity.setdefault(track.identity, []).append(track)
    invalid = [identity for identity, rows in by_identity.items() if len(rows) < 2]
    if invalid:
        raise MetricAdapterError(
            "every train identity must have at least two cross-camera tracks"
        )
    identities = {identity: index for index, identity in enumerate(sorted(by_identity))}
    vectors = _normalize_numpy(np.stack([track.vector for track in train_tracks]))
    labels = np.asarray(
        [identities[track.identity] for track in train_tracks], dtype=np.int64
    )
    return vectors, labels


def train_metric_adapter(
    tracks: Sequence[TrackEmbedding],
    config: AdapterConfig,
    device: torch.device,
) -> tuple[TorchVectorAdapter, float]:
    vectors, labels = _train_arrays(tracks)
    torch.manual_seed(config.seed)
    random.seed(config.seed)
    np.random.seed(config.seed)
    model = ResidualMetricAdapter(
        vectors.shape[1], config.rank, config.residual_scale
    ).to(device)
    head = ArcFaceHead(
        vectors.shape[1],
        int(labels.max()) + 1,
        margin=config.arc_margin,
    ).to(device)
    optimizer = torch.optim.AdamW(
        (*model.parameters(), *head.parameters()),
        lr=config.learning_rate,
        weight_decay=0.01,
    )
    source = torch.as_tensor(vectors, dtype=torch.float32, device=device)
    target = torch.as_tensor(labels, dtype=torch.long, device=device)
    source_geometry = source @ source.T
    final_loss = float("nan")
    for _ in range(config.epochs):
        noisy = F.normalize(source + torch.randn_like(source) * 0.004, dim=-1)
        dropped = F.normalize(
            F.dropout(source, p=0.04, training=True),
            dim=-1,
        )
        augmented = torch.cat((noisy, dropped), dim=0)
        augmented_labels = torch.cat((target, target), dim=0)
        embeddings = model(augmented)
        base_embeddings = model(source)
        classification = F.cross_entropy(
            head(embeddings, augmented_labels), augmented_labels
        )
        triplet = _batch_hard_triplet_loss(
            embeddings, augmented_labels, config.triplet_margin
        )
        contrastive = _supervised_contrastive_loss(embeddings, augmented_labels)
        geometry = F.smooth_l1_loss(
            base_embeddings @ base_embeddings.T, source_geometry
        )
        preserve = (1.0 - (base_embeddings * source).sum(dim=1)).mean()
        loss = (
            classification
            + 0.75 * triplet
            + 0.25 * contrastive
            + config.geometry_weight * geometry
            + config.preserve_weight * preserve
        )
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_((*model.parameters(), *head.parameters()), 5.0)
        optimizer.step()
        final_loss = float(loss.detach().cpu())
    return TorchVectorAdapter(model, device), final_loss


def _transform_tracks(
    tracks: Sequence[TrackEmbedding], adapter: VectorAdapter
) -> list[TrackEmbedding]:
    vectors = adapter.transform(np.stack([track.vector for track in tracks]))
    return [
        TrackEmbedding(
            track_id=track.track_id,
            identity=track.identity,
            role=track.role,
            camera=track.camera,
            split=track.split,
            vector=vectors[index],
            frame_count=track.frame_count,
        )
        for index, track in enumerate(tracks)
    ]


def _open_set_models(seed: int) -> dict[str, ProbabilityModel]:
    return {
        "linear-l2-0.001": LinearProbabilityHead(regularization=0.001),
        "linear-l2-0.01": LinearProbabilityHead(regularization=0.01),
        "tanh-h16-l2-0.001": TanhProbabilityHead(
            hidden_size=16, regularization=0.001, seed=seed
        ),
        "tanh-h32-l2-0.01": TanhProbabilityHead(
            hidden_size=32, regularization=0.01, seed=seed + 1
        ),
    }


def _fit_open_set_head(
    tracks: Sequence[TrackEmbedding], episodes: int, seed: int
) -> tuple[str, ProbabilityModel, float, OpenSetBatch, dict[str, int | float], bool]:
    train_batch = build_training_episodes(tracks, episodes, seed)
    validation_batch = extract_open_set_batch(
        [track for track in tracks if track.split == "validation"]
    )
    labels = (train_batch.known & train_batch.top1_correct).astype(np.int32)
    best: (
        tuple[
            tuple[float, ...],
            str,
            ProbabilityModel,
            float,
            dict[str, int | float],
            bool,
        ]
        | None
    ) = None
    for name, model in _open_set_models(seed).items():
        model.fit(train_batch.features, labels)
        probabilities = model.predict_proba(validation_batch.features)[:, 1]
        threshold, metrics, threshold_feasible = select_threshold(
            validation_batch, probabilities
        )
        feasible = (
            threshold_feasible
            and metrics.known_rank1 >= 0.85
            and metrics.known_recall_at5 >= 0.95
        )
        key = (
            float(feasible),
            metrics.automatic_decision_accuracy,
            metrics.known_rank1,
            -metrics.distractor_false_match_rate,
            -metrics.false_reject_rate,
        )
        row_metrics = asdict(metrics)
        candidate = (key, name, model, threshold, row_metrics, feasible)
        if best is None or candidate[0] > best[0]:
            best = candidate
    if best is None:
        raise MetricAdapterError("open-set head search produced no candidate")
    return best[1], best[2], best[3], validation_batch, best[4], best[5]


def _configs(seed: int) -> list[AdapterConfig]:
    return [
        AdapterConfig(
            name="identity-solider",
            rank=0,
            residual_scale=0.0,
            epochs=0,
            learning_rate=0.0,
            arc_margin=0.0,
            triplet_margin=0.0,
            geometry_weight=0.0,
            preserve_weight=0.0,
            seed=seed,
        ),
        AdapterConfig(
            name="arc-triplet-r32-preserve",
            rank=32,
            residual_scale=0.25,
            epochs=300,
            learning_rate=0.001,
            arc_margin=0.30,
            triplet_margin=0.20,
            geometry_weight=1.0,
            preserve_weight=0.25,
            seed=seed + 1,
        ),
        AdapterConfig(
            name="arc-triplet-r64-balanced",
            rank=64,
            residual_scale=0.40,
            epochs=400,
            learning_rate=0.0007,
            arc_margin=0.35,
            triplet_margin=0.25,
            geometry_weight=0.50,
            preserve_weight=0.15,
            seed=seed + 2,
        ),
        AdapterConfig(
            name="arc-triplet-r128-hard-negative",
            rank=128,
            residual_scale=0.50,
            epochs=500,
            learning_rate=0.0005,
            arc_margin=0.40,
            triplet_margin=0.30,
            geometry_weight=0.25,
            preserve_weight=0.10,
            seed=seed + 3,
        ),
    ]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Train validation-selected ArcFace/Triplet residual metric adapters on "
            "PRID2011 train identities and evaluate the sealed test once"
        )
    )
    parser.add_argument("--track-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--head-output", type=Path, required=True)
    parser.add_argument("--episodes", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260729)
    parser.add_argument("--device", default="cuda")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.device.startswith("cuda") and not torch.cuda.is_available():
        raise MetricAdapterError("CUDA was requested but is unavailable")
    device = torch.device(args.device)
    tracks = load_track_cache(args.track_cache)
    candidates: list[CandidateRow] = []
    best: (
        tuple[
            tuple[float, ...],
            AdapterConfig,
            VectorAdapter,
            ProbabilityModel,
            float,
            str,
        ]
        | None
    ) = None
    for config in _configs(args.seed):
        if config.epochs == 0:
            adapter: VectorAdapter = IdentityVectorAdapter()
            final_loss = None
        else:
            adapter, final_loss = train_metric_adapter(tracks, config, device)
        transformed = _transform_tracks(tracks, adapter)
        (
            head_name,
            open_set_model,
            threshold,
            _,
            validation_metrics,
            feasible,
        ) = _fit_open_set_head(transformed, args.episodes, config.seed)
        key = (
            float(feasible),
            float(validation_metrics["automatic_decision_accuracy"]),
            float(validation_metrics["known_rank1"]),
            -float(validation_metrics["distractor_false_match_rate"]),
            -float(validation_metrics["false_reject_rate"]),
        )
        candidates.append(
            {
                "name": config.name,
                "config": asdict(config),
                "threshold": threshold,
                "openSetHead": head_name,
                "validationFeasible": feasible,
                "validationMetrics": validation_metrics,
                "finalLoss": final_loss,
            }
        )
        selected = (
            key,
            config,
            adapter,
            open_set_model,
            threshold,
            head_name,
        )
        if best is None or selected[0] > best[0]:
            best = selected
    if best is None:
        raise MetricAdapterError("metric adapter search produced no candidate")

    _, config, adapter, open_set_model, threshold, head_name = best
    transformed = _transform_tracks(tracks, adapter)
    test_batch = extract_open_set_batch(
        [track for track in transformed if track.split == "test"]
    )
    test_probabilities = open_set_model.predict_proba(test_batch.features)[:, 1]
    test_metrics = decision_metrics(test_batch, test_probabilities >= threshold)
    selected_row = next(row for row in candidates if row["name"] == config.name)
    result = {
        "schemaVersion": "prid2011-track-evaluation-v1",
        "status": "valid",
        "method": "SOLIDER residual metric adapter plus open-set verifier",
        "selectionProtocol": (
            "ArcFace/Triplet adapters fitted on train identities only; adapter, "
            "open-set head, and threshold selected on validation identities; "
            "sealed test evaluated once after selection"
        ),
        "promotionContract": {
            "crossCamera": True,
            "identityDisjoint": True,
            "sealedTest": True,
            "thresholdSelectedOnValidationOnly": True,
            "projectCctvEvidence": False,
        },
        "featureNames": FEATURE_NAMES,
        "selected": selected_row,
        "candidates": candidates,
        "testMetrics": asdict(test_metrics),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    metadata = {
        "schemaVersion": "prid2011-metric-adapter-v1",
        "adapterConfig": asdict(config),
        "openSetFeatureNames": FEATURE_NAMES,
        "openSetHead": head_name,
        "openSetThreshold": threshold,
        "openSetState": {
            name: value.tolist() for name, value in open_set_model.state().items()
        },
    }
    adapter_state = adapter.state()
    args.head_output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.head_output,
        metadata=np.asarray(json.dumps(metadata, sort_keys=True)),
        down_weight=adapter_state.get(
            "down.weight", np.empty((0, 0), dtype=np.float32)
        ),
        up_weight=adapter_state.get(
            "up.weight", np.empty((0, 0), dtype=np.float32)
        ),
    )
    print(
        json.dumps(
            {
                "selected": selected_row,
                "testMetrics": asdict(test_metrics),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

