from qwen_backend.distillation import DistillationSample
from qwen_backend.evaluation import StudentPrediction, evaluate_predictions


def reference() -> DistillationSample:
    return DistillationSample.model_validate(
        {
            "schemaVersion": "distillation-v1",
            "sampleId": "sample-001",
            "imagePath": "candidate.jpg",
            "attributes": {"color": "red", "clothing": "jacket", "objectName": "person"},
            "decision": "match",
            "confidence": 0.9,
            "provenance": {
                "sourceKind": "open_model",
                "teacherModel": "local",
                "promptVersion": "v1",
                "sourceHash": "0" * 64,
            },
        }
    )


def test_evaluation_counts_valid_and_invalid_json() -> None:
    student_output = (
        '{"decision":"match","attributes":{"color":"red",'
        '"clothing":"jacket","objectName":"person"},"confidence":0.8}'
    )
    predictions = (
        StudentPrediction.model_validate(
            {
                "sampleId": "sample-001",
                "output": student_output,
            }
        ),
        StudentPrediction.model_validate({"sampleId": "sample-001", "output": "not-json"}),
    )

    report = evaluate_predictions((reference(),), predictions)

    assert report.total == 1
    assert report.json_valid == 1
    assert report.decision_accuracy == 1
    assert report.color_accuracy == 1
    assert report.clothing_accuracy == 1

