from scripts.build_chirla_manifest import benchmark_role, build_records


def test_benchmark_role_preserves_official_reid_roles() -> None:
    assert benchmark_role("train", "train_0") == "train"
    assert benchmark_role("test", "test_0") == "validation"
    assert benchmark_role("train", "train_1") == "gallery"
    assert benchmark_role("test", "test_1") == "query"


def test_build_records_excludes_json_and_keeps_source_identity() -> None:
    rows = [
        {
            "sourcePath": (
                "benchmark/reid/long_term/train/train_0/seq_001/"
                "imgs/camera_1/7/frame_1.png"
            ),
            "scenario": "long_term",
            "split": "train",
            "subset": "train_0",
            "sequenceId": "seq_001",
            "cameraId": "camera_1",
            "identityGroupId": "7",
            "frameName": "frame_1.png",
            "localPath": "local/frame_1.png",
            "fileId": "file-1",
            "sha256": "a" * 64,
            "bytes": 10,
        },
        {"sourcePath": "benchmark/reid/long_term/train/train_0/seq_001/camera_1.json"},
    ]

    records = build_records(rows)

    assert len(records) == 1
    assert records[0].identityGroupId == "7"
    assert records[0].benchmarkRole == "train"
    assert records[0].identityIsProjectReviewed is False
