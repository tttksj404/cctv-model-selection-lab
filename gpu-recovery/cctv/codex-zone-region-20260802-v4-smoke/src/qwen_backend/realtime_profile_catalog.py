from __future__ import annotations

from dataclasses import dataclass

from qwen_backend.realtime_models import ColorTarget


@dataclass(frozen=True, slots=True)
class ProfileColor:
    target: ColorTarget
    ko: str
    en: str
    aliases: tuple[str, ...]


COLORS = (
    ProfileColor("black", "검은색", "black", ("검은색", "검정색", "검은", "검정", "블랙")),
    ProfileColor("gray", "회색", "gray", ("회색", "그레이")),
    ProfileColor("navy", "남색", "navy", ("남색", "네이비")),
    ProfileColor("white", "흰색", "white", ("흰색", "하얀색", "흰", "하얀", "화이트")),
    ProfileColor("red", "빨간색", "red", ("빨간색", "빨강", "빨간", "레드")),
    ProfileColor("blue", "파란색", "blue", ("파란색", "파랑", "파란", "블루")),
    ProfileColor("green", "초록색", "green", ("초록색", "녹색", "초록", "그린")),
    ProfileColor("brown", "갈색", "brown", ("갈색", "브라운")),
    ProfileColor("yellow", "노란색", "yellow", ("노란색", "노랑", "노란", "옐로우")),
    ProfileColor("pink", "분홍색", "pink", ("분홍색", "분홍", "핑크")),
    ProfileColor("orange", "주황색", "orange", ("주황색", "주황", "오렌지")),
    ProfileColor("purple", "보라색", "purple", ("보라색", "보라", "퍼플")),
)

TOP_TERMS = (
    "상의",
    "티셔츠",
    "셔츠",
    "반팔",
    "긴팔",
    "니트",
    "스웨터",
    "후드",
    "자켓",
    "재킷",
    "점퍼",
    "코트",
    "옷",
)
BOTTOM_TERMS = ("하의", "바지", "청바지", "슬랙스", "치마", "반바지")

STYLE_PROMPTS = (
    (
        ("민소매", "나시"),
        "민소매",
        "a sleeveless top with bare shoulders",
        "a shirt with sleeves covering the shoulders",
    ),
    (
        ("반팔",),
        "반팔",
        "a short-sleeve shirt with bare forearms",
        "a long-sleeve shirt, sweater, or jacket",
    ),
    (
        ("긴팔",),
        "긴팔",
        "a long-sleeve shirt covering the forearms",
        "a short-sleeve or sleeveless shirt",
    ),
    (
        ("후드", "후디"),
        "후드",
        "a hooded sweatshirt or hoodie",
        "a top without a hood",
    ),
    (
        ("니트", "스웨터"),
        "니트",
        "a knitted sweater",
        "a plain t-shirt or non-knitted jacket",
    ),
    (
        ("자켓", "재킷", "점퍼"),
        "재킷",
        "a person wearing a jacket",
        "a person without a jacket",
    ),
    (
        ("코트",),
        "코트",
        "a person wearing a long coat",
        "a person without a coat",
    ),
)

HAIR_PROMPTS = (
    (
        ("넘긴 머리", "넘긴머리", "올백", "포마드"),
        "넘긴 머리",
        "a portrait with swept-back or side-parted hair and visible forehead",
        "a portrait with straight bangs covering the forehead",
    ),
    (
        ("단발",),
        "단발머리",
        "a portrait with a short bob haircut",
        "a portrait with long hair below the shoulders",
    ),
    (
        ("긴 머리", "긴머리", "장발"),
        "긴 머리",
        "a portrait with long hair below the shoulders",
        "a portrait with short cropped hair",
    ),
    (
        ("짧은 머리", "짧은머리", "숏컷"),
        "짧은 머리",
        "a portrait with short cropped hair",
        "a portrait with long hair below the shoulders",
    ),
    (
        ("곱슬", "파마", "웨이브"),
        "곱슬머리",
        "a portrait with curly or wavy hair",
        "a portrait with straight hair",
    ),
    (
        ("앞머리", "뱅"),
        "앞머리",
        "a portrait with bangs covering part of the forehead",
        "a portrait with a fully visible forehead and swept-back hair",
    ),
)
