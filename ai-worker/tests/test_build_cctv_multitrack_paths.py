from scripts.build_cctv_multitrack_draft import _short_path_key


def test_short_path_key_is_stable_and_bounded_for_recording_ids() -> None:
    long_video_id = (
        "20260806T090245050745Z_2c8ce522-e6b9-4551-a250-42ef6d48b330__3479-32105.window"
    )

    first = _short_path_key(long_video_id)
    second = _short_path_key(long_video_id)

    assert first == second
    assert first.startswith("video-")
    assert len(first) <= 24
    assert first != _short_path_key(long_video_id + "-other")
