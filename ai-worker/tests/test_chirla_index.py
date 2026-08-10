from scripts.chirla_index import (
    parse_chirla_index,
    parse_chirla_url,
    safe_relative_path,
    select_reid_files,
)


def test_parse_chirla_png_keeps_identity_and_camera_provenance() -> None:
    raw = (
        "https://download.scidb.cn/download?fileId=abc&path="
        "/V2/CHIRLA_dataset/benchmark/reid/multi_camera_long_term/test/test_0/"
        "seq_026/imgs/camera_1_2023-06-08-12:29:08/5/frame_3469.png"
    )

    parsed = parse_chirla_url(raw)

    assert parsed is not None
    assert parsed.scenario == "multi_camera_long_term"
    assert parsed.split == "test"
    assert parsed.subset == "test_0"
    assert parsed.sequence_id == "seq_026"
    assert parsed.camera_id == "camera_1_2023-06-08-12:29:08"
    assert parsed.identity_group_id == "5"
    assert parsed.frame_name == "frame_3469.png"


def test_parse_chirla_json_has_label_file_provenance_without_fake_identity() -> None:
    raw = (
        "https://download.scidb.cn/download?fileId=abc&path="
        "/V2/CHIRLA_dataset/benchmark/reid/multi_camera_long_term/test/test_0/"
        "seq_026/camera_1_2023-06-08-12:29:08.json"
    )

    parsed = parse_chirla_url(raw)

    assert parsed is not None
    assert parsed.extension == ".json"
    assert parsed.camera_id == "camera_1_2023-06-08-12:29:08"
    assert parsed.identity_group_id is None


def test_select_reid_files_keeps_metadata_when_sampling() -> None:
    content = "\n".join(
        [
            "https://download.scidb.cn/download?fileId=j&path=/V2/CHIRLA_dataset/benchmark/reid/long_term/test/test_0/seq_001/camera_1.json",
            *[
                f"https://download.scidb.cn/download?fileId={i}&path=/V2/CHIRLA_dataset/benchmark/reid/long_term/test/test_1/seq_001/imgs/camera_1/1/frame_{i}.png"
                for i in range(10)
            ],
        ]
    )

    selected = select_reid_files(parse_chirla_index(content), scenario="long_term", max_files=4)

    assert len(selected) == 4
    assert any(item.extension == ".json" for item in selected)


def test_select_reid_files_round_robins_subset_and_identity() -> None:
    rows = []
    for subset in ("train_0", "test_0"):
        for identity in ("1", "2"):
            rows.extend(
                f"https://download.scidb.cn/download?fileId={subset}-{identity}-{i}&path="
                f"/V2/CHIRLA_dataset/benchmark/reid/long_term/test/{subset}/seq_001/"
                f"imgs/camera_1/{identity}/frame_{i}.png"
                for i in range(3)
            )

    selected = select_reid_files(
        parse_chirla_index("\n".join(rows)), scenario="long_term", max_files=5
    )

    assert {(item.subset, item.identity_group_id) for item in selected} == {
        ("test_0", "1"),
        ("test_0", "2"),
        ("train_0", "1"),
        ("train_0", "2"),
    }


def test_safe_relative_path_removes_windows_drive_separator() -> None:
    actual = safe_relative_path("videos/seq/camera_1_12:00:00.avi")
    assert actual == "videos/seq/camera_1_12-00-00.avi"

