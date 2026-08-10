from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol

from .distillation import DistillationSample, read_distillation_samples

TeacherMode = Literal["manifest"]


class TeacherAdapterError(ValueError):
    pass


class TeacherAdapter(Protocol):
    def load(self, input_path: Path) -> tuple[DistillationSample, ...]: ...


class ManifestTeacherAdapter:
    def load(self, input_path: Path) -> tuple[DistillationSample, ...]:
        return read_distillation_samples(input_path)


def build_teacher_adapter(mode: str) -> TeacherAdapter:
    if mode != "manifest":
        raise TeacherAdapterError(
            f"unsupported teacher mode: {mode}; "
            "only manifest is enabled before local model adapters"
        )
    return ManifestTeacherAdapter()

