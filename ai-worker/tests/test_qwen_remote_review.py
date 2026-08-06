from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from qwen_backend.qwen_review_runtime import QwenReviewRuntime


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_remote_qwen_review_sends_crop_and_parses_openai_response(
    monkeypatch,
    tmp_path: Path,
) -> None:
    image = tmp_path / "candidate.jpg"
    image.write_bytes(b"fake-jpeg")
    requests: list[tuple[str, dict[str, str], dict[str, object]]] = []
    response_body = {
        "choices": [
            {
                "message": {
                    "content": (
                        "```json\n"
                        '{"decision":"match","attributes":{"color":"white"},'
                        '"confidence":0.8,"semantic_match_score":0.9,'
                        '"failure_reason":null}\n'
                        "```"
                    )
                }
            }
        ]
    }

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> _Response:
        assert timeout == 12.0
        body = json.loads(request.data.decode("utf-8"))
        requests.append((request.full_url, dict(request.headers), body))
        return _Response(json.dumps(response_body).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    review, status = QwenReviewRuntime(
        enabled=True,
        top_k=5,
        provider_mode="remote",
        remote_base_url="http://gpu.example:8000/v1",
        remote_model="qwen-active",
        remote_api_key="test-key",
        remote_timeout_seconds=12.0,
    ).review(
        image,
        case_id=1,
        camera_id=2,
        track_id=3,
        prompt="white shirt, black pants",
    )

    assert status == "used:remote"
    assert review is not None
    assert review.decision == "match"
    assert review.semantic_score == 0.9
    assert len(requests) == 1
    endpoint, headers, body = requests[0]
    assert endpoint == "http://gpu.example:8000/v1/chat/completions"
    assert headers["Authorization"] == "Bearer test-key"
    content = body["messages"][0]["content"]
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_remote_qwen_review_fails_closed_without_endpoint(tmp_path: Path) -> None:
    review, status = QwenReviewRuntime(
        enabled=True,
        top_k=5,
        provider_mode="remote",
    ).review(
        tmp_path / "candidate.jpg",
        case_id=1,
        camera_id=2,
        track_id=3,
        prompt="white shirt",
    )

    assert review is None
    assert status == "unavailable:remote_endpoint_not_configured"
