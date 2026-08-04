from __future__ import annotations

from typing import cast

import httpx
from auth_support import TEST_INTERNAL_HEADERS
from fastapi.testclient import TestClient
from pydantic import JsonValue, SecretStr
from zone_probability_support import TEST_SIGNING_KEY, evidence, request

from qwen_backend.config import Settings
from qwen_backend.research_app import create_research_app as create_app


def _post(payload: dict[str, JsonValue]) -> httpx.Response:
    with TestClient(
        create_app(
            Settings(
                provider="mock",
                probability_evidence_signing_key=SecretStr(TEST_SIGNING_KEY),
            )
        ),
        headers=TEST_INTERNAL_HEADERS,
    ) as client:
        return cast(httpx.Client, client).post("/v1/search-routing/probability", json=payload)


def test_probability_endpoint_rejects_unprovenanced_scores() -> None:
    payload = request().model_dump(mode="json", by_alias=True)
    payload["evidence"] = [
        {
            "eventId": "unsafe-event",
            "zoneId": 1,
            "cameraId": "1-1",
            "trackId": "unsafe-track",
            "correlationGroupId": "unsafe-global-track",
            "observationGroupId": "recording-1:camera-1-1:segment-1",
            "observedAt": "2026-08-01T03:00:00Z",
            "trackQuality": 1.0,
            "signals": [{"signalKind": "reid", "probability": 0.99}],
        }
    ]

    assert _post(payload).status_code == 422


def test_probability_endpoint_rejects_well_formed_but_untrusted_hashes() -> None:
    payload = request(evidence_items=(evidence(),)).model_dump(mode="json", by_alias=True)
    payload["evidence"][0]["signals"][0]["modelSha256"] = "b" * 64

    response = _post(payload)

    assert response.status_code == 422
    assert response.json()["code"] == "untrusted_probability_provenance"


def test_probability_endpoint_rejects_operating_point_value_tampering() -> None:
    payload = request(evidence_items=(evidence(),)).model_dump(mode="json", by_alias=True)
    payload["cameras"][0]["sensitivity"] = 0.999999
    payload["cameras"][0]["falsePositiveRate"] = 0.000001

    response = _post(payload)

    assert response.status_code == 422
    assert response.json()["code"] == "untrusted_probability_provenance"


def test_probability_endpoint_rejects_missing_request_signature() -> None:
    payload = request(evidence_items=(evidence(),)).model_dump(mode="json", by_alias=True)
    payload.pop("evidenceSignature")

    response = _post(payload)

    assert response.status_code == 422
    assert response.json()["code"] == "untrusted_probability_provenance"


def test_probability_endpoint_rejects_invalid_request_signature() -> None:
    payload = request(evidence_items=(evidence(),)).model_dump(mode="json", by_alias=True)
    payload["evidenceSignature"] = "a" * 64

    response = _post(payload)

    assert response.status_code == 422
    assert response.json()["code"] == "untrusted_probability_provenance"


def test_probability_endpoint_rejects_probability_tampering_after_signature() -> None:
    payload = request(evidence_items=(evidence(),)).model_dump(mode="json", by_alias=True)
    evidence_items = cast(list[dict[str, object]], payload["evidence"])
    signals = cast(list[dict[str, object]], evidence_items[0]["signals"])
    signals[0]["probability"] = 0.999999

    response = _post(payload)

    assert response.status_code == 422
    assert response.json()["code"] == "untrusted_probability_provenance"


def test_probability_endpoint_returns_ranked_operator_review_response() -> None:
    payload = request(evidence_items=(evidence(),)).model_dump(mode="json", by_alias=True)

    response = _post(payload)

    assert response.status_code == 200
    body = cast(dict[str, object], response.json())
    assert body["caseId"] == "case-77"
    assert body["operatorReviewRequired"] is True
    assert body["autoMatchAllowed"] is False
    assert body["candidatePoolStatus"] == "candidate_found"
    assert body["mostLikelyZoneId"] == 3
    zone_posterior = cast(list[dict[str, object]], body["zonePosterior"])
    zone_summaries = cast(list[dict[str, object]], body["zoneCandidateSummaries"])
    assert body["mostLikelyZoneProbability"] == zone_posterior[2]["probability"]
    assert zone_summaries[2]["topCandidateEventId"] == "event-1"
    next_camera_id = body["nextCameraId"]
    assert isinstance(next_camera_id, str)
    assert next_camera_id.startswith("3-")


def test_probability_endpoint_rejects_replayed_signed_request() -> None:
    payload = request(evidence_items=(evidence(),)).model_dump(mode="json", by_alias=True)
    app = create_app(
        Settings(
            provider="mock",
            probability_evidence_signing_key=SecretStr(TEST_SIGNING_KEY),
        )
    )

    with TestClient(app, headers=TEST_INTERNAL_HEADERS) as client:
        first = cast(httpx.Client, client).post("/v1/search-routing/probability", json=payload)
        replay = cast(httpx.Client, client).post("/v1/search-routing/probability", json=payload)

    assert first.status_code == 200
    assert replay.status_code == 409
    assert replay.json()["code"] == "replayed_or_stale_probability_request"
