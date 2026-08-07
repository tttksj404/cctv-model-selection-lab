from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from qwen_backend.config import get_settings
from qwen_backend.providers import ModelAnalysisPayload, ProviderError, Qwen3VLProvider
from qwen_backend.schemas import CandidateAnalysisRequest, SearchCondition

logger = logging.getLogger(__name__)

QwenReviewDecision = Literal["match", "review", "reject"]


@dataclass(frozen=True, slots=True)
class QwenReview:
    decision: QwenReviewDecision
    confidence: float
    semantic_score: float

    @property
    def score(self) -> float:
        if self.decision == "reject":
            return 0.0
        if self.decision == "match":
            return max(0.0, min(1.0, self.semantic_score * (0.5 + (0.5 * self.confidence))))
        return max(0.0, min(1.0, self.semantic_score * self.confidence))


class RemoteQwenReviewClient:
    """OpenAI-compatible remote Qwen/VLM client for a GPU inference server.

    The worker sends a small local crop as a data URL, so the GPU server never
    needs access to the notebook filesystem or the central storage credentials.
    The base URL is expected to be the vLLM ``/v1`` URL, for example
    ``http://gpu-host:8000/v1``.
    """

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None,
        timeout_seconds: float,
    ) -> None:
        normalized = base_url.strip().rstrip("/")
        if not normalized:
            raise ValueError("remote Qwen base URL must not be blank")
        self._endpoint = (
            normalized
            if normalized.endswith("/chat/completions")
            else f"{normalized}/chat/completions"
        )
        self._model = model
        self._api_key = api_key.strip() if api_key and api_key.strip() else None
        self._timeout_seconds = timeout_seconds

    def analyze(
        self,
        image_path: Path,
        *,
        case_id: int,
        camera_id: int,
        track_id: int,
        prompt: str,
    ) -> ModelAnalysisPayload:
        try:
            image_bytes = image_path.read_bytes()
        except OSError as error:
            raise ProviderError("remote Qwen crop could not be read") from error
        if not image_bytes:
            raise ProviderError("remote Qwen crop is empty")
        if len(image_bytes) > 10 * 1024 * 1024:
            raise ProviderError("remote Qwen crop exceeds the 10 MiB request limit")

        mime_type = mimetypes.guess_type(image_path.name)[0] or "image/jpeg"
        data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        request_prompt = (
            "Inspect the candidate image against the search condition. "
            "Return only one JSON object with keys decision (match/review/reject), "
            "attributes (color/clothing/texture/object_name; texture is an array), "
            "confidence (0 to 1), semantic_match_score (0 to 1), and failure_reason. "
            "Do not add markdown. "
            f"Search condition: {prompt[:400]}"
        )
        body = {
            "model": self._model,
            "temperature": 0.0,
            "max_tokens": 256,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": request_prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        }
        headers = {"Content-Type": "application/json"}
        if self._api_key is not None:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request = urllib.request.Request(
            self._endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                response_body = response.read()
        except urllib.error.HTTPError as error:
            raise ProviderError(f"remote Qwen returned HTTP {error.code}") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise ProviderError("remote Qwen endpoint is unavailable") from error

        try:
            response_json = json.loads(response_body.decode("utf-8"))
            raw_content = _extract_chat_content(response_json)
            return ModelAnalysisPayload.model_validate(_parse_model_json(raw_content))
        except (UnicodeDecodeError, TypeError, ValueError, KeyError, IndexError) as error:
            raise ProviderError("remote Qwen returned an invalid response") from error


class QwenReviewRuntime:
    """Qwen review adapter used after deterministic candidate generation."""

    def __init__(
        self,
        *,
        enabled: bool,
        top_k: int,
        provider_mode: Literal["local", "remote"] = "local",
        remote_base_url: str | None = None,
        remote_model: str = "qwen-active",
        remote_api_key: str | None = None,
        remote_timeout_seconds: float = 90.0,
    ) -> None:
        self._enabled = enabled
        self._top_k = top_k
        self._provider_mode = provider_mode
        self._remote_base_url = remote_base_url
        self._remote_model = remote_model
        self._remote_api_key = remote_api_key
        self._remote_timeout_seconds = remote_timeout_seconds
        self._provider: Qwen3VLProvider | None = None
        self._remote_provider: RemoteQwenReviewClient | None = None
        self._warmup_status: str | None = None

    @property
    def top_k(self) -> int:
        return self._top_k

    def warm_up(self) -> str:
        """Prepare the configured local/remote reviewer once for this process."""

        if self._warmup_status is not None:
            return self._warmup_status
        if not self._enabled:
            self._warmup_status = "disabled"
            return self._warmup_status

        if self._provider_mode == "remote":
            try:
                if not self._remote_base_url:
                    self._warmup_status = "unavailable:remote_endpoint_not_configured"
                else:
                    self._remote_provider = RemoteQwenReviewClient(
                        base_url=self._remote_base_url,
                        model=self._remote_model,
                        api_key=self._remote_api_key,
                        timeout_seconds=self._remote_timeout_seconds,
                    )
                    self._warmup_status = "ready:remote"
            except (ProviderError, OSError, RuntimeError, TypeError, ValueError) as error:
                self._warmup_status = f"unavailable:remote:{type(error).__name__}"
                logger.warning("remote Qwen reviewer warm-up unavailable: %s", error)
            return self._warmup_status

        try:
            provider_name = (
                os.environ.get("QWEN_PROVIDER") or get_settings().provider
            ).strip().lower()
            if provider_name != "qwen":
                self._warmup_status = "unavailable:QWEN_PROVIDER_is_not_qwen"
                return self._warmup_status
            if self._provider is None:
                self._provider = Qwen3VLProvider(get_settings())
            self._provider.warm_up()
        except (ProviderError, OSError, RuntimeError, TypeError, ValueError) as error:
            self._warmup_status = f"unavailable:{type(error).__name__}"
            logger.warning("local Qwen reviewer warm-up unavailable: %s", error)
        else:
            self._warmup_status = "ready:local"
        return self._warmup_status

    def review(
        self,
        image_path: Path,
        *,
        case_id: int,
        camera_id: int,
        track_id: int,
        prompt: str,
    ) -> tuple[QwenReview | None, str]:
        if not self._enabled:
            return None, "disabled"
        if self._warmup_status is not None and self._warmup_status.startswith("unavailable:"):
            return None, self._warmup_status

        if self._provider_mode == "remote":
            if not self._remote_base_url:
                return None, "unavailable:remote_endpoint_not_configured"
            try:
                if self._remote_provider is None:
                    self._remote_provider = RemoteQwenReviewClient(
                        base_url=self._remote_base_url,
                        model=self._remote_model,
                        api_key=self._remote_api_key,
                        timeout_seconds=self._remote_timeout_seconds,
                    )
                analysis = self._remote_provider.analyze(
                    image_path,
                    case_id=case_id,
                    camera_id=camera_id,
                    track_id=track_id,
                    prompt=prompt,
                )
            except (ProviderError, OSError, RuntimeError, TypeError, ValueError) as error:
                return None, f"failed:remote:{type(error).__name__}"
            return _to_review(analysis), "used:remote"

        # Prefer an explicitly exported process variable, but also honor the
        # project's dotenv/Pydantic settings.  The notebook worker loads its
        # dotenv file before lazy model creation; reading only os.environ here
        # would silently fall back to mock when Settings already saw qwen from
        # .env.
        provider_name = (
            os.environ.get("QWEN_PROVIDER") or get_settings().provider
        ).strip().lower()
        if provider_name != "qwen":
            return None, "unavailable:QWEN_PROVIDER_is_not_qwen"
        if self._provider is None:
            self._provider = Qwen3VLProvider(get_settings())
        try:
            analysis = self._provider.review(
                CandidateAnalysisRequest(
                    caseId=str(case_id),
                    cameraId=str(camera_id),
                    trackId=str(track_id),
                    imagePath=str(image_path),
                    searchCondition=SearchCondition(
                        clothing=prompt[:80] if prompt.strip() else None,
                        objectName="person",
                    ),
                )
            )
        except (ProviderError, OSError, RuntimeError, TypeError, ValueError) as error:
            return None, f"failed:{type(error).__name__}"
        return _to_review(analysis), "used:local"


def _to_review(analysis: Any) -> QwenReview:
    semantic_score = (
        analysis.semantic_match_score
        if analysis.semantic_match_score is not None
        else analysis.confidence
    )
    return QwenReview(
        decision=analysis.decision,
        confidence=analysis.confidence,
        semantic_score=semantic_score,
    )


def _extract_chat_content(response: Any) -> str:
    response_object = cast(dict[str, Any], response)
    choices_value = response_object.get("choices")
    if not isinstance(choices_value, list) or not choices_value:
        raise ValueError("remote Qwen response has no choices")
    choices: list[Any] = cast(list[Any], choices_value)
    first_choice_value: Any = choices[0]
    if not isinstance(first_choice_value, dict):
        raise ValueError("remote Qwen response has an invalid choice")
    first_choice = cast(dict[str, Any], first_choice_value)
    message_value: Any = first_choice.get("message")
    if not isinstance(message_value, dict):
        raise ValueError("remote Qwen response has no message")
    message = cast(dict[str, Any], message_value)
    content: Any = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in cast(list[Any], content):
            if isinstance(item, dict) and "text" in item:
                text_parts.append(str(cast(Any, item["text"])))
        if text_parts:
            return "".join(text_parts)
    raise ValueError("remote Qwen response has no text content")


def _parse_model_json(raw: str) -> dict[str, Any]:
    cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Qwen output did not contain JSON")
    value = json.loads(cleaned[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("Qwen output JSON was not an object")
    return cast(dict[str, Any], value)
