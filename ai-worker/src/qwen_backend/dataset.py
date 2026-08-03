from json import JSONDecodeError
from pathlib import Path

from .schemas import TeacherLabel


class DatasetError(ValueError):
    pass


def read_teacher_labels(path: Path) -> tuple[TeacherLabel, ...]:
    labels: list[TeacherLabel] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise DatasetError(f"could not read teacher labels: {path}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            labels.append(TeacherLabel.model_validate_json(line))
        except (JSONDecodeError, ValueError) as exc:
            raise DatasetError(f"invalid teacher label at line {line_number}") from exc
    return tuple(labels)
