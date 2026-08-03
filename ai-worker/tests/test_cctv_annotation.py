from qwen_backend.cctv_annotation import PersonDetection, select_primary_detection


def test_primary_detection_uses_largest_person_box() -> None:
    detections = (
        PersonDetection(x1=10.0, y1=10.0, x2=40.0, y2=80.0, confidence=0.92),
        PersonDetection(x1=100.0, y1=20.0, x2=500.0, y2=900.0, confidence=0.61),
    )

    selected = select_primary_detection(detections)

    assert selected == detections[1]


def test_primary_detection_returns_none_for_empty_frame() -> None:
    assert select_primary_detection(()) is None
