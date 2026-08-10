from __future__ import annotations

from collections.abc import Sequence
from typing import TypedDict

import numpy as np
from numpy.typing import NDArray


class IdentityRetrievalMetrics(TypedDict):
    query_count: int
    gallery_identity_count: int
    rank1: float
    recall_at_5: float
    recall_at_10: float
    identity_mrr: float
    rank1_ci95_low: float
    rank1_ci95_high: float


class MetricContractError(ValueError):
    pass


def compute_identity_retrieval_metrics(
    scores: NDArray[np.floating],
    query_identities: Sequence[str],
    gallery_identities: Sequence[str],
    bootstrap_seed: int = 20260724,
) -> IdentityRetrievalMetrics:
    expected_shape = (len(query_identities), len(gallery_identities))
    if scores.shape != expected_shape:
        raise MetricContractError(
            "scores shape does not match query/gallery identities"
        )

    ranks: list[int] = []
    reciprocal_ranks: list[float] = []
    gallery_array = np.asarray(gallery_identities)
    for index, identity in enumerate(query_identities):
        order = np.argsort(-scores[index], kind="stable")
        relevant = np.flatnonzero(gallery_array[order] == identity)
        if len(relevant) == 0:
            raise MetricContractError(
                f"query identity {identity!r} is missing from gallery"
            )
        rank = int(relevant[0]) + 1
        ranks.append(rank)
        reciprocal_ranks.append(1.0 / rank)

    rank_array = np.asarray(ranks, dtype=np.int64)
    reciprocal = np.asarray(reciprocal_ranks, dtype=np.float64)
    generator = np.random.default_rng(bootstrap_seed)
    samples = generator.integers(0, len(rank_array), size=(2000, len(rank_array)))
    bootstrap_rank1 = (rank_array[samples] == 1).mean(axis=1)
    return {
        "query_count": len(query_identities),
        "gallery_identity_count": len(gallery_identities),
        "rank1": float((rank_array == 1).mean()),
        "recall_at_5": float((rank_array <= 5).mean()),
        "recall_at_10": float((rank_array <= 10).mean()),
        "identity_mrr": float(reciprocal.mean()),
        "rank1_ci95_low": float(np.quantile(bootstrap_rank1, 0.025)),
        "rank1_ci95_high": float(np.quantile(bootstrap_rank1, 0.975)),
    }

