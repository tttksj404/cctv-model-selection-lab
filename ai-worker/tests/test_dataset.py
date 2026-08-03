from pathlib import Path

import pytest

from qwen_backend.dataset import DatasetError, read_teacher_labels


def test_teacher_fixture_is_typed() -> None:
    labels = read_teacher_labels(Path("fixtures/teacher_labels.jsonl"))
    assert len(labels) == 1
    assert labels[0].teacher_model == "sonnet-5"


def test_malformed_teacher_label_reports_line(tmp_path: Path) -> None:
    path = tmp_path / "labels.jsonl"
    path.write_text(
        '{"schemaVersion":"v1","sampleId":"s1","caseId":"c1","imagePath":"/x.jpg",'
        '"attributes":{"color":"red"},"candidateQuality":"review","reason":"r",'
        '"teacherModel":"sonnet-5","teacherVersion":"v1",'
        '"promptVersion":"p1","sourceHash":"h1"}\nnot-json\n',
        encoding="utf-8",
    )
    with pytest.raises(DatasetError, match="line 2"):
        read_teacher_labels(path)
