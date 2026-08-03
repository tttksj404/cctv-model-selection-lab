from __future__ import annotations

import hashlib
import json
import zlib
from dataclasses import dataclass
from pathlib import Path

if __package__:
    from scripts.zone_policy_paired_metrics import RecomputedReplay, recompute
    from scripts.zone_policy_replay_seed import expected_target_state
    from scripts.zone_policy_result_schema import (
        EXPECTED_MAX_SCANS,
        EXPECTED_PAIRED_EVIDENCE_SHA256,
        POLICIES,
        JsonValue,
        MissionValidationInputError,
        parse_json_text,
        strict_int,
    )
else:
    from zone_policy_paired_metrics import RecomputedReplay, recompute
    from zone_policy_replay_seed import expected_target_state
    from zone_policy_result_schema import (
        EXPECTED_MAX_SCANS,
        EXPECTED_PAIRED_EVIDENCE_SHA256,
        POLICIES,
        JsonValue,
        MissionValidationInputError,
        parse_json_text,
        strict_int,
    )

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = (REPOSITORY_ROOT / "experiments" / "results" / "evidence").resolve()
EVIDENCE_FIELDS = frozenset({"artifact", "format", "recordCount", "sha256"})
RAW_FIELDS = frozenset(
    {
        "cohort",
        "episodeId",
        "episodeIndex",
        "cellSeed",
        "scenario",
        "operatingPoint",
        "policy",
        "targetState",
        "scansToResolution",
        "resolvedWithinBudget",
        "finalTop1Correct",
        "falseZoneActivation",
    }
)


@dataclass(frozen=True, slots=True)
class EvidenceSpec:
    base_seed: int
    episodes_per_cell: int
    scenarios: tuple[str, ...]
    operating_points: tuple[str, ...]

    @property
    def expected_record_count(self) -> int:
        return (
            self.episodes_per_cell
            * len(self.scenarios)
            * len(self.operating_points)
            * 2
            * len(POLICIES)
        )


def write_paired_records(path: Path, records: list[dict[str, JsonValue]]) -> str:
    ordered = sorted(
        records,
        key=lambda item: (
            str(item["cohort"]),
            str(item["episodeId"]),
            str(item["policy"]),
        ),
    )
    text = (
        "\n".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for item in ordered
        )
        + "\n"
    )
    compressed = zlib.compress(text.encode(), level=9)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(compressed)
    return hashlib.sha256(compressed).hexdigest()


def _read_records(compressed: bytes) -> list[dict[str, JsonValue]]:
    text = zlib.decompress(compressed).decode()
    records: list[dict[str, JsonValue]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        record = parse_json_text(line)
        if not isinstance(record, dict):
            raise MissionValidationInputError(
                f"paired evidence line {line_number} must be a JSON object"
            )
        records.append(record)
    return records


def _record_valid(record: dict[str, JsonValue], spec: EvidenceSpec) -> bool:
    cohort = record.get("cohort")
    scenario = record.get("scenario")
    point = record.get("operatingPoint")
    episode_index = strict_int(record.get("episodeIndex"))
    cell_seed = strict_int(record.get("cellSeed"))
    scans = strict_int(record.get("scansToResolution"), minimum=1)
    policy = record.get("policy")
    target = record.get("targetState")
    booleans = tuple(
        record.get(key)
        for key in (
            "resolvedWithinBudget",
            "finalTop1Correct",
            "falseZoneActivation",
        )
    )
    if (
        set(record) != set(RAW_FIELDS)
        or cohort not in {"selection", "sealed_test"}
        or not isinstance(scenario, str)
        or scenario not in spec.scenarios
        or not isinstance(point, str)
        or point not in spec.operating_points
        or episode_index is None
        or episode_index >= spec.episodes_per_cell
        or policy not in POLICIES
        or scans is None
        or scans > EXPECTED_MAX_SCANS + 1
        or not all(isinstance(value, bool) for value in booleans)
    ):
        return False
    target_valid = (
        isinstance(target, int) and not isinstance(target, bool) and 1 <= target <= 4
    ) or target in {"outside", "unknown"}
    cohort_offset = 0 if cohort == "selection" else 10_000_000
    expected_seed = (
        spec.base_seed
        + cohort_offset
        + spec.scenarios.index(scenario) * 1_000_000
        + spec.operating_points.index(point) * 100_000
        + episode_index
    )
    expected_episode = f"{cohort}:{scenario}:{point}:{episode_index}"
    return bool(
        target_valid
        and cell_seed == expected_seed
        and target == expected_target_state(expected_seed, scenario)
        and record.get("episodeId") == expected_episode
        and record.get("resolvedWithinBudget") is (scans <= EXPECTED_MAX_SCANS)
    )


def _episodes_are_coherent(records: list[dict[str, JsonValue]]) -> bool:
    contexts: dict[tuple[JsonValue, JsonValue], tuple[JsonValue, ...]] = {}
    episode_policies: dict[tuple[JsonValue, JsonValue], set[JsonValue]] = {}
    for record in records:
        key = (record["cohort"], record["episodeId"])
        context = (
            record["episodeIndex"],
            record["cellSeed"],
            record["scenario"],
            record["operatingPoint"],
            record["targetState"],
        )
        previous = contexts.setdefault(key, context)
        if previous != context:
            return False
        episode_policies.setdefault(key, set()).add(record["policy"])
    return all(policies == set(POLICIES) for policies in episode_policies.values())


def _resolve_evidence_path(artifact: JsonValue) -> Path | None:
    if not isinstance(artifact, str) or Path(artifact).is_absolute():
        return None
    path = (REPOSITORY_ROOT / artifact).resolve()
    try:
        path.relative_to(EVIDENCE_ROOT)
    except ValueError:
        return None
    return path


def validate_and_recompute(
    evidence: dict[str, JsonValue], spec: EvidenceSpec
) -> tuple[bool, bool, RecomputedReplay | None]:
    if set(evidence) != set(EVIDENCE_FIELDS):
        return False, False, None
    path = _resolve_evidence_path(evidence.get("artifact"))
    if path is None:
        return False, False, None
    if not path.is_file() or evidence.get("format") != "jsonl-zlib-v1":
        return True, False, None
    try:
        compressed = path.read_bytes()
    except OSError:
        return True, False, None
    digest = hashlib.sha256(compressed).hexdigest()
    hash_matches = bool(
        digest == EXPECTED_PAIRED_EVIDENCE_SHA256
        and evidence.get("sha256") == EXPECTED_PAIRED_EVIDENCE_SHA256
    )
    if not hash_matches:
        return True, False, None
    try:
        records = _read_records(compressed)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        MissionValidationInputError,
        zlib.error,
    ):
        return True, True, None
    if (
        strict_int(evidence.get("recordCount")) != spec.expected_record_count
        or len(records) != spec.expected_record_count
        or not all(_record_valid(record, spec) for record in records)
    ):
        return True, True, None
    unique_keys = {(record["cohort"], record["episodeId"], record["policy"]) for record in records}
    if len(unique_keys) != spec.expected_record_count or not _episodes_are_coherent(records):
        return True, True, None
    try:
        return True, True, recompute(records)
    except MissionValidationInputError:
        return True, True, None


__all__ = ["EvidenceSpec", "RecomputedReplay", "validate_and_recompute", "write_paired_records"]
