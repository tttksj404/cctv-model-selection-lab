from __future__ import annotations

from qwen_backend.realtime_models import (
    AppearanceProfile,
    AppearanceProfileError,
    AppearanceRequirements,
)
from qwen_backend.realtime_profile_catalog import (
    BOTTOM_TERMS,
    COLORS,
    HAIR_PROMPTS,
    STYLE_PROMPTS,
    TOP_TERMS,
    ProfileColor,
)


def _term_positions(text: str, terms: tuple[str, ...]) -> tuple[int, ...]:
    positions: list[int] = []
    for term in terms:
        start = 0
        while (index := text.find(term, start)) >= 0:
            positions.append(index)
            start = index + len(term)
    return tuple(positions)


def _nearest_color(text: str, garment_terms: tuple[str, ...]) -> ProfileColor | None:
    garment_positions = _term_positions(text, garment_terms)
    if not garment_positions:
        return None
    best: tuple[int, int, ProfileColor] | None = None
    for color in COLORS:
        for position in _term_positions(text, color.aliases):
            nearest_garment = min(
                garment_positions,
                key=lambda garment: abs(position - garment),
            )
            distance = abs(position - nearest_garment)
            follows_garment = int(position > nearest_garment)
            candidate = (distance, follows_garment, color)
            if best is None or candidate[:2] < best[:2]:
                best = candidate
    return best[2] if best is not None and best[0] <= 18 else None


def _first_prompt(
    text: str,
    rows: tuple[tuple[tuple[str, ...], str, str, str], ...],
) -> tuple[str, str, str] | None:
    for aliases, label, positive, negative in rows:
        if any(alias in text for alias in aliases):
            return label, positive, negative
    return None


def _glasses_prompt(text: str) -> tuple[str, str, str] | None:
    absent = ("안경 미착용", "안경 없음", "안경을 쓰지", "안경을 안", "노안경")
    if any(term in text for term in absent):
        return (
            "안경 미착용",
            "a close-up portrait with bare eyes and no eyeglasses",
            "a close-up portrait wearing clear eyeglasses",
        )
    if "선글라스" in text:
        return (
            "선글라스",
            "a close-up portrait wearing dark sunglasses",
            "a close-up portrait without sunglasses",
        )
    if "안경" in text:
        return (
            "안경",
            "a close-up portrait wearing clear eyeglasses",
            "a close-up portrait with bare eyes and no eyeglasses",
        )
    return None


def _extra_prompts(text: str) -> list[str]:
    prompts = [
        prompt
        for aliases, prompt in (
            (("남자", "남성"), "an adult man"),
            (("여자", "여성"), "an adult woman"),
        )
        if any(alias in text for alias in aliases)
    ]
    presence_rows = (
        (
            ("백팩", "배낭"),
            ("백팩 없음", "배낭 없음", "백팩 미착용", "배낭 미착용"),
            "carrying a backpack",
            "not carrying a backpack",
        ),
        (
            ("가방",),
            ("가방 없음", "가방 미착용", "가방을 들지", "가방을 안"),
            "carrying a bag",
            "not carrying a bag",
        ),
        (
            ("모자", "캡"),
            ("모자 없음", "모자 미착용", "모자를 쓰지", "모자를 안"),
            "wearing a hat",
            "not wearing a hat",
        ),
        (
            ("마스크",),
            ("마스크 없음", "마스크 미착용", "마스크를 쓰지", "마스크를 안"),
            "wearing a face mask",
            "not wearing a face mask",
        ),
        (
            ("수염",),
            ("수염 없음", "수염이 없음", "면도한"),
            "with facial hair",
            "clean-shaven with no facial hair",
        ),
    )
    for present_aliases, absent_aliases, present_prompt, absent_prompt in presence_rows:
        if any(alias in text for alias in absent_aliases):
            prompts.append(absent_prompt)
        elif any(alias in text for alias in present_aliases):
            prompts.append(present_prompt)
    return prompts


def parse_appearance_profile(
    description_ko: str,
    *,
    clip_query_en: str | None = None,
) -> AppearanceProfile:
    description = " ".join(description_ko.strip().split())
    if not description:
        raise AppearanceProfileError("인상착의는 비워둘 수 없습니다.")

    top_color = _nearest_color(description, TOP_TERMS)
    bottom_color = _nearest_color(description, BOTTOM_TERMS)
    style = _first_prompt(description, STYLE_PROMPTS)
    hair = _first_prompt(description, HAIR_PROMPTS)
    glasses = _glasses_prompt(description)
    extras = _extra_prompts(description)

    details = list(extras)
    if top_color is not None:
        details.append(f"wearing {top_color.en} upper clothing")
    if bottom_color is not None:
        details.append(f"wearing {bottom_color.en} pants or lower clothing")
    if style is not None:
        details.append(style[1])
    if hair is not None:
        details.append(hair[1])
    if glasses is not None:
        details.append(glasses[1])
    if not details:
        raise AppearanceProfileError(
            "지원되는 인상착의가 없습니다. 색상·상의·하의·안경·머리·가방·모자 중 "
            "하나 이상을 입력하세요."
        )

    query = clip_query_en or (
        "a full-body CCTV image of a person " + ", ".join(details)
    )
    exclusion = (
        "a full-body CCTV image of a different person whose visible clothing "
        "and attributes do not match " + ", ".join(details)
    )
    style_label, style_positive, style_negative = style or (
        "상의 형태 미지정",
        "a clearly visible upper garment",
        "an upper garment hidden from view",
    )
    hair_label, hair_positive, hair_negative = hair or (
        "머리 형태 미지정",
        "a portrait with clearly visible hair",
        "a portrait with hair hidden from view",
    )
    glasses_label, glasses_positive, glasses_negative = glasses or (
        "안경 여부 미지정",
        "a close-up portrait with clearly visible eyes",
        "a close-up portrait with the face hidden from view",
    )
    return AppearanceProfile(
        description_ko=description,
        clip_query_en=query,
        exclusion_query_en=exclusion,
        top_color_target=top_color.target if top_color is not None else None,
        top_color_label_ko=(
            f"{top_color.ko} 상의" if top_color is not None else "상의 색상 미지정"
        ),
        bottom_color_target=bottom_color.target if bottom_color is not None else None,
        bottom_color_label_ko=(
            f"{bottom_color.ko} 하의" if bottom_color is not None else "하의 색상 미지정"
        ),
        glasses_label_ko=glasses_label,
        glasses_positive_en=glasses_positive,
        glasses_negative_en=glasses_negative,
        hair_label_ko=hair_label,
        hair_positive_en=hair_positive,
        hair_negative_en=hair_negative,
        upper_style_label_ko=style_label,
        upper_style_positive_en=style_positive,
        upper_style_negative_en=style_negative,
        requirements=AppearanceRequirements(
            top_color=top_color is not None,
            bottom_color=bottom_color is not None,
            glasses=glasses is not None,
            hair=hair is not None,
            upper_style=style is not None,
            identity=False,
        ),
    )
