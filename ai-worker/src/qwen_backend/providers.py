import json
import re
import time
from threading import Lock
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from .config import Settings
from .schemas import CandidateAnalysisRequest, CandidateAnalysisResponse, CandidateAttributes


class ProviderError(RuntimeError):
    pass


class ProviderUnavailable(ProviderError):
    pass


class ProviderInferenceError(ProviderError):
    pass


class AnalysisProvider(Protocol):
    @property
    def model_loaded(self) -> bool: ...

    @property
    def model_version(self) -> str: ...

    def analyze(self, request: CandidateAnalysisRequest) -> CandidateAnalysisResponse: ...


class ModelAnalysisPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    decision: Literal["match", "review", "reject"]
    attributes: CandidateAttributes
    confidence: float = Field(ge=0.0, le=1.0)
    semantic_match_score: float | None = Field(
        default=None, alias="semanticMatchScore", ge=0.0, le=1.0
    )
    failure_reason: str | None = Field(default=None, alias="failureReason")


class MockProvider:
    model_loaded = False
    model_version = "qwen3vl-mock-0.1"

    def analyze(self, request: CandidateAnalysisRequest) -> CandidateAnalysisResponse:
        started = time.perf_counter()
        condition = request.search_condition
        attributes = CandidateAttributes(
            color=condition.color or "unknown",
            clothing=condition.clothing or "unknown",
            object_name=condition.object_name or "person",
        )
        decision = "review"
        return CandidateAnalysisResponse(
            case_id=request.case_id,
            camera_id=request.camera_id,
            track_id=request.track_id,
            decision=decision,
            attributes=attributes,
            confidence=0.5,
            semanticMatchScore=0.5,
            modelVersion=self.model_version,
            latencyMs=(time.perf_counter() - started) * 1000,
            failureReason=None,
        )


class Qwen3VLProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._processor: Any | None = None
        self._model: Any | None = None
        self._process_vision_info: Any | None = None
        self._load_lock = Lock()
        self._inference_lock = Lock()

    @property
    def model_loaded(self) -> bool:
        return self._model is not None

    @property
    def model_version(self) -> str:
        return self._settings.model_version

    def _load(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            if not self._settings.model_path.is_dir():
                raise ProviderUnavailable("Qwen checkpoint is unavailable")
            try:
                import torch
                from qwen_vl_utils import process_vision_info
                from transformers import AutoModelForImageTextToText, AutoProcessor
            except ImportError as exc:
                raise ProviderUnavailable("Qwen runtime dependencies are missing") from exc
            try:
                self._processor = AutoProcessor.from_pretrained(
                    self._settings.model_path, local_files_only=True
                )
                self._model = AutoModelForImageTextToText.from_pretrained(
                    self._settings.model_path,
                    torch_dtype=torch.bfloat16,
                    attn_implementation="flash_attention_2",
                    device_map=self._settings.device_map,
                    local_files_only=True,
                )
                self._process_vision_info = process_vision_info
            except (OSError, RuntimeError, ValueError) as exc:
                raise ProviderUnavailable("Qwen checkpoint could not be loaded locally") from exc

    def analyze(self, request: CandidateAnalysisRequest) -> CandidateAnalysisResponse:
        with self._inference_lock:
            self._load()
            assert self._processor is not None
            assert self._model is not None
            assert self._process_vision_info is not None
            started = time.perf_counter()
            prompt = (
                "Inspect the candidate image against the search condition. "
                "Return only one JSON object with keys decision (match/review/reject), "
                "attributes (color/clothing/texture/object_name; texture is an array), "
                "confidence (0 to 1), semantic_match_score (0 to 1), and "
                "failure_reason. Do not add markdown. "
                f"Search condition: {request.search_condition.model_dump_json()}"
            )
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": request.image_path},
                        {"type": "text", "text": prompt},
                    ],
                }
            ]
            try:
                text = self._processor.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )
                image_inputs, video_inputs = self._process_vision_info(messages)
                inputs = self._processor(
                    text=[text],
                    images=image_inputs,
                    videos=video_inputs,
                    padding=True,
                    return_tensors="pt",
                )
                inputs = inputs.to(self._model.device)
                generated_ids = self._model.generate(
                    **inputs, max_new_tokens=self._settings.max_new_tokens
                )
                trimmed_ids = [
                    out_ids[len(in_ids) :]
                    for in_ids, out_ids in zip(inputs.input_ids, generated_ids, strict=True)
                ]
                raw = self._processor.batch_decode(
                    trimmed_ids, skip_special_tokens=True, clean_up_tokenization_spaces=False
                )[0]
                payload = ModelAnalysisPayload.model_validate(self._parse_json(raw))
                return CandidateAnalysisResponse(
                    case_id=request.case_id,
                    camera_id=request.camera_id,
                    track_id=request.track_id,
                    decision=payload.decision,
                    attributes=payload.attributes,
                    confidence=payload.confidence,
                    semanticMatchScore=(
                        payload.semantic_match_score
                        if payload.semantic_match_score is not None
                        else payload.confidence
                    ),
                    modelVersion=self.model_version,
                    latencyMs=(time.perf_counter() - started) * 1000,
                    failureReason=payload.failure_reason,
                )
            except (OSError, RuntimeError, TypeError, ValueError, KeyError, IndexError) as exc:
                raise ProviderInferenceError(
                    "Qwen inference did not produce a valid response"
                ) from exc

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        cleaned = raw.strip().removeprefix("```json").removesuffix("```").strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match is None:
            raise ProviderInferenceError("Qwen output did not contain JSON")
        value = json.loads(match.group(0))
        if not isinstance(value, dict):
            raise ProviderInferenceError("Qwen output JSON was not an object")
        return value
