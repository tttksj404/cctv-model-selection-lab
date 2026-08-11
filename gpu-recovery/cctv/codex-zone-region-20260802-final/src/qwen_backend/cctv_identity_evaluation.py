from __future__ import annotations

from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Split = Literal[
    "train",
    "validation",
    "gallery",
    "test",
    "test_landscape",
    "test_portrait_fisheye",
]
TargetRole = Literal["target", "distractor", "unknown"]
Decision = Literal["match", "review", "reject"]
ReportStatus = Literal[
    "valid",
    "blocked_missing_identity_labels",
    "blocked_missing_gallery",
]
TEST_SPLITS: frozenset[Split] = frozenset({"test", "test_landscape", "test_portrait_fisheye"})
GALLERY_SPLITS: frozenset[Split] = frozenset({"gallery"})
TEST_ONLY_SPLITS: frozenset[Split] = frozenset({"test_landscape", "test_portrait_fisheye"})


class CCTVDataError(ValueError):
    pass


class TrackReference(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    case_id: str = Field(alias="caseId", min_length=1)
    video_id: str = Field(alias="videoId", min_length=1)
    camera_id: str = Field(alias="cameraId", min_length=1)
    condition_group_id: str = Field(alias="conditionGroupId", min_length=1)
    track_id: str = Field(alias="trackId", min_length=1)
    split: Split
    target_role: TargetRole = Field(alias="targetRole")
    identity_group_id: str | None = Field(default=None, alias="identityGroupId")
    frame_count: int = Field(default=0, alias="frameCount", ge=0)


class RankedCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    identity_group_id: str = Field(alias="identityGroupId", min_length=1)
    score: float


class TrackRetrievalPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    query_track_id: str = Field(alias="queryTrackId", min_length=1)
    candidates: tuple[RankedCandidate, ...] = Field(min_length=1)
    decision: Decision


class CCTVIdentityReport(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    model_name: str = Field(alias="modelName")
    status: ReportStatus
    test_track_count: int = Field(alias="testTrackCount", ge=0)
    predicted_track_count: int = Field(alias="predictedTrackCount", ge=0)
    known_query_count: int = Field(alias="knownQueryCount", ge=0)
    unlabeled_target_count: int = Field(alias="unlabeledTargetCount", ge=0)
    query_without_gallery_count: int = Field(alias="queryWithoutGalleryCount", ge=0)
    gallery_track_count: int = Field(alias="galleryTrackCount", ge=0)
    gallery_identity_count: int = Field(alias="galleryIdentityCount", ge=0)
    missing_prediction_count: int = Field(alias="missingPredictionCount", ge=0)
    unknown_query_count: int = Field(alias="unknownQueryCount", ge=0)
    distractor_query_count: int = Field(alias="distractorQueryCount", ge=0)
    rank1: float | None = None
    recall_at_5: float | None = Field(default=None, alias="recallAt5")
    recall_at_10: float | None = Field(default=None, alias="recallAt10")
    mean_average_precision: float | None = Field(default=None, alias="meanAveragePrecision")
    mean_inp: float | None = Field(default=None, alias="meanINP")
    false_match_rate: float | None = Field(default=None, alias="falseMatchRate")
    false_reject_rate: float | None = Field(default=None, alias="falseRejectRate")
    review_rate: float | None = Field(default=None, alias="reviewRate")


def validate_track_split(references: tuple[TrackReference, ...]) -> None:
    track_to_splits: dict[str, set[Split]] = defaultdict(set)
    identity_to_splits: dict[str, set[Split]] = defaultdict(set)
    seen_tracks: set[str] = set()

    for reference in references:
        if reference.track_id in seen_tracks:
            raise CCTVDataError(f"duplicate trackId: {reference.track_id}")
        seen_tracks.add(reference.track_id)
        track_to_splits[reference.track_id].add(reference.split)
        if reference.identity_group_id is not None:
            identity_to_splits[reference.identity_group_id].add(reference.split)

    leaked_tracks = [track_id for track_id, splits in track_to_splits.items() if len(splits) > 1]
    if leaked_tracks:
        raise CCTVDataError(f"track appears in multiple splits: {sorted(leaked_tracks)}")

    leaked_identities = [
        identity_id
        for identity_id, splits in identity_to_splits.items()
        if len(splits - GALLERY_SPLITS) > 1
        and not (splits - GALLERY_SPLITS).issubset(TEST_ONLY_SPLITS)
    ]
    if leaked_identities:
        raise CCTVDataError(
            f"identityGroupId appears in multiple splits: {sorted(leaked_identities)}"
        )


def _average_precision(relevant_ranks: list[int], gallery_size: int) -> float:
    if not relevant_ranks or gallery_size == 0:
        return 0.0
    precision_sum = sum(
        (rank_index + 1) / rank for rank_index, rank in enumerate(relevant_ranks)
    )
    return precision_sum / min(len(relevant_ranks), gallery_size)


def _inp(relevant_ranks: list[int]) -> float:
    if not relevant_ranks:
        return 0.0
    last_relevant_rank = relevant_ranks[-1]
    return len(relevant_ranks) / last_relevant_rank


def evaluate_identity_predictions(
    references: tuple[TrackReference, ...],
    predictions: tuple[TrackRetrievalPrediction, ...],
    *,
    model_name: str,
) -> CCTVIdentityReport:
    validate_track_split(references)
    reference_by_track = {reference.track_id: reference for reference in references}
    prediction_by_track: dict[str, TrackRetrievalPrediction] = {}
    for prediction in predictions:
        if prediction.query_track_id in prediction_by_track:
            raise CCTVDataError(f"duplicate prediction queryTrackId: {prediction.query_track_id}")
        if prediction.query_track_id not in reference_by_track:
            raise CCTVDataError(f"prediction has unknown queryTrackId: {prediction.query_track_id}")
        candidate_ids = [candidate.identity_group_id for candidate in prediction.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise CCTVDataError(
                f"duplicate candidate identityGroupId for queryTrackId: {prediction.query_track_id}"
            )
        prediction_by_track[prediction.query_track_id] = prediction

    test_references = [reference for reference in references if reference.split in TEST_SPLITS]
    gallery_references = [
        reference for reference in references if reference.split in GALLERY_SPLITS
    ]
    gallery_identity_ids = {
        reference.identity_group_id
        for reference in gallery_references
        if reference.identity_group_id is not None
    }
    known_queries = [
        reference
        for reference in test_references
        if reference.identity_group_id is not None and reference.target_role == "target"
    ]
    unlabeled_target_queries = [
        reference
        for reference in test_references
        if reference.target_role == "target" and reference.identity_group_id is None
    ]
    unknown_queries = [
        reference
        for reference in test_references
        if reference.target_role == "unknown"
    ]
    distractor_queries = [
        reference
        for reference in test_references
        if reference.target_role == "distractor"
    ]

    predicted_count = sum(
        reference.track_id in prediction_by_track for reference in test_references
    )
    missing_prediction_count = sum(
        reference.track_id not in prediction_by_track for reference in known_queries
    )
    missing_gallery_count = sum(
        reference.identity_group_id not in gallery_identity_ids
        for reference in known_queries
    )
    queries_without_gallery = missing_gallery_count

    if gallery_identity_ids:
        for prediction in predictions:
            unknown_gallery_ids = [
                candidate.identity_group_id
                for candidate in prediction.candidates
                if candidate.identity_group_id not in gallery_identity_ids
            ]
            if unknown_gallery_ids:
                raise CCTVDataError(
                    "candidate identityGroupId is not present in gallery: "
                    f"{sorted(set(unknown_gallery_ids))}"
                )

    rank_hits = {1: 0, 5: 0, 10: 0}
    average_precisions: list[float] = []
    inps: list[float] = []
    false_reject_count = 0
    non_target_count = len(unknown_queries) + len(distractor_queries)
    false_match_count = 0
    review_count = 0
    for reference in test_references:
        prediction = prediction_by_track.get(reference.track_id)
        expected_match = (
            reference.target_role == "target" and reference.identity_group_id is not None
        )
        if prediction is None:
            if expected_match:
                false_reject_count += 1
                queries_without_gallery += 1
                average_precisions.append(0.0)
                inps.append(0.0)
            continue
        if prediction.decision == "review":
            review_count += 1

        if expected_match:
            if prediction.decision == "reject":
                false_reject_count += 1
        else:
            if prediction.decision == "match":
                false_match_count += 1

        if not expected_match:
            continue
        ranked_candidates = sorted(
            prediction.candidates, key=lambda candidate: candidate.score, reverse=True
        )
        ranked_ids = [candidate.identity_group_id for candidate in ranked_candidates]
        relevant_ranks = [
            index
            for index, identity_id in enumerate(ranked_ids, start=1)
            if identity_id == reference.identity_group_id
        ]
        if not relevant_ranks:
            queries_without_gallery += 1
            average_precisions.append(0.0)
            inps.append(0.0)
            continue
        for cutoff in rank_hits:
            rank_hits[cutoff] += int(any(rank <= cutoff for rank in relevant_ranks))
        average_precisions.append(_average_precision(relevant_ranks, len(ranked_ids)))
        inps.append(_inp(relevant_ranks))

    if unlabeled_target_queries or not known_queries:
        return CCTVIdentityReport(
            modelName=model_name,
            status="blocked_missing_identity_labels",
            testTrackCount=len(test_references),
            predictedTrackCount=predicted_count,
            knownQueryCount=len(known_queries),
            unlabeledTargetCount=len(unlabeled_target_queries),
            queryWithoutGalleryCount=queries_without_gallery,
            galleryTrackCount=len(gallery_references),
            galleryIdentityCount=len(gallery_identity_ids),
            missingPredictionCount=missing_prediction_count,
            unknownQueryCount=len(unknown_queries),
            distractorQueryCount=len(distractor_queries),
        )

    if not gallery_references or missing_gallery_count:
        return CCTVIdentityReport(
            modelName=model_name,
            status="blocked_missing_gallery",
            testTrackCount=len(test_references),
            predictedTrackCount=predicted_count,
            knownQueryCount=len(known_queries),
            unlabeledTargetCount=0,
            queryWithoutGalleryCount=queries_without_gallery,
            galleryTrackCount=len(gallery_references),
            galleryIdentityCount=len(gallery_identity_ids),
            missingPredictionCount=missing_prediction_count,
            unknownQueryCount=len(unknown_queries),
            distractorQueryCount=len(distractor_queries),
        )

    denominator = len(known_queries)
    decision_denominator = max(predicted_count, 1)
    return CCTVIdentityReport(
        modelName=model_name,
        status="valid",
        testTrackCount=len(test_references),
        predictedTrackCount=predicted_count,
        knownQueryCount=len(known_queries),
        unlabeledTargetCount=0,
        queryWithoutGalleryCount=queries_without_gallery,
        galleryTrackCount=len(gallery_references),
        galleryIdentityCount=len(gallery_identity_ids),
        missingPredictionCount=missing_prediction_count,
        unknownQueryCount=len(unknown_queries),
        distractorQueryCount=len(distractor_queries),
        rank1=rank_hits[1] / denominator,
        recallAt5=rank_hits[5] / denominator,
        recallAt10=rank_hits[10] / denominator,
        meanAveragePrecision=sum(average_precisions) / denominator,
        meanINP=sum(inps) / denominator,
        falseMatchRate=false_match_count / max(non_target_count, 1),
        falseRejectRate=false_reject_count / denominator,
        reviewRate=review_count / decision_denominator,
    )
