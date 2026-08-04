from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import NoReturn, TypeAlias, cast

JsonScalar: TypeAlias = bool | int | float | str | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class MissionValidationInputError(ValueError):
    pass


def _reject_nonfinite_json(token: str) -> NoReturn:
    raise MissionValidationInputError(f"non-finite JSON number is forbidden: {token}")


def _parse_finite_json_float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise MissionValidationInputError(f"overflowed JSON number is forbidden: {token}")
    return value


def _reject_duplicate_object_keys(
    pairs: list[tuple[str, JsonValue]],
) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in payload:
            raise MissionValidationInputError(f"duplicate JSON object key is forbidden: {key}")
        payload[key] = value
    return payload


def parse_json_text(text: str) -> JsonValue:
    try:
        return cast(
            JsonValue,
            json.loads(
                text,
                object_pairs_hook=_reject_duplicate_object_keys,
                parse_constant=_reject_nonfinite_json,
                parse_float=_parse_finite_json_float,
            ),
        )
    except json.JSONDecodeError as exc:
        raise MissionValidationInputError(
            f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc


def parse_json_bytes(data: bytes, *, label: str = "JSON input") -> JsonValue:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MissionValidationInputError(f"{label} must be valid UTF-8") from exc
    return parse_json_text(text)


def load_json(path: Path) -> JsonValue:
    return parse_json_bytes(path.read_bytes(), label=f"JSON input {path}")


def canonical_json_sha256_value(payload: JsonValue) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def canonical_json_sha256(path: Path) -> str:
    return canonical_json_sha256_value(load_json(path))


def finite_float(value: JsonValue) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) else None


def strict_int(value: JsonValue, *, minimum: int = 0) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        return None
    return value


def same_scalar(left: JsonValue, right: JsonValue) -> bool:
    return type(left) is type(right) and left == right


def json_exact_equal(left: JsonValue, right: JsonValue) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict) and isinstance(right, dict):
        return set(left) == set(right) and all(
            json_exact_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(
            json_exact_equal(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    return left == right
