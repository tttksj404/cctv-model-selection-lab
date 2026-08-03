import pytest

from qwen_backend.realtime_models import AppearanceProfile, AppearanceProfileError


def test_parse_requested_gray_short_sleeve_profile() -> None:
    profile = AppearanceProfile.from_description(
        "회색 반팔 검은색 바지 안경 넘긴머리 남자"
    )

    assert profile.top_color_target == "gray"
    assert profile.bottom_color_target == "black"
    assert profile.glasses_label_ko == "안경"
    assert profile.hair_label_ko == "넘긴 머리"
    assert profile.upper_style_label_ko == "반팔"
    assert "adult man" in profile.clip_query_en


def test_parse_navy_knit_profile_without_inventing_hair() -> None:
    profile = AppearanceProfile.from_description(
        "남색 니트옷 안경착용 검은색 바지 남자"
    )

    assert profile.top_color_target == "navy"
    assert profile.bottom_color_target == "black"
    assert profile.upper_style_label_ko == "니트"
    assert profile.requirements.hair is False


def test_parse_explicitly_no_glasses() -> None:
    profile = AppearanceProfile.from_description("흰색 셔츠 청바지 안경 없음 여자")

    assert profile.glasses_label_ko == "안경 미착용"
    assert "no eyeglasses" in profile.glasses_positive_en
    assert profile.requirements.glasses is True


def test_empty_appearance_is_rejected() -> None:
    with pytest.raises(AppearanceProfileError, match="비워둘 수 없습니다"):
        AppearanceProfile.from_description("   ")


def test_explicit_absent_hat_and_mask_are_not_reversed() -> None:
    profile = AppearanceProfile.from_description(
        "회색 반팔 검은색 바지 모자 없음 마스크 없음 남자"
    )

    assert "not wearing a hat" in profile.clip_query_en
    assert "not wearing a face mask" in profile.clip_query_en


def test_custom_clip_query_still_requires_parsed_counterexample_attributes() -> None:
    with pytest.raises(AppearanceProfileError, match="하나 이상"):
        AppearanceProfile.from_description(
            "키 175",
            clip_query_en="a tall person",
        )
