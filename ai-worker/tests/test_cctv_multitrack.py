from qwen_backend.cctv_multitrack import (
    TrackObservation,
    format_track_id,
    select_representative_observations,
)


def test_format_track_id_when_video_and_tracker_id_are_valid() -> None:
    # Given
    video_id = "IMG_3617"

    # When
    track_id = format_track_id(video_id, 7)

    # Then
    assert track_id == "IMG_3617-track-0007"


def test_select_representatives_when_track_is_long_spreads_frames() -> None:
    # Given
    observations = tuple(
        TrackObservation(
            frame_index=frame_index,
            timestamp_ms=frame_index * 100,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.9,
        )
        for frame_index in range(10)
    )

    # When
    selected = select_representative_observations(observations, limit=3)

    # Then
    assert tuple(item.frame_index for item in selected) == (0, 4, 9)


def test_select_representatives_when_limit_exceeds_track_keeps_all() -> None:
    # Given
    observations = (
        TrackObservation(
            frame_index=3,
            timestamp_ms=300,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.8,
        ),
        TrackObservation(
            frame_index=1,
            timestamp_ms=100,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.7,
        ),
    )

    # When
    selected = select_representative_observations(observations, limit=4)

    # Then
    assert tuple(item.frame_index for item in selected) == (1, 3)


def test_select_representatives_when_limit_is_one_uses_middle_frame() -> None:
    observations = tuple(
        TrackObservation(
            frame_index=frame_index,
            timestamp_ms=frame_index * 100,
            bbox=(0.0, 0.0, 10.0, 20.0),
            confidence=0.9,
        )
        for frame_index in range(5)
    )

    selected = select_representative_observations(observations, limit=1)

    assert tuple(item.frame_index for item in selected) == (2,)

