import { describe, expect, it } from "vitest";
import {
  APPEARANCE_CATEGORIES,
  APPEARANCE_KEYS,
  APPEARANCE_LIMITS,
  COLOR_OPTIONS,
  getAppearanceCategory,
  parseAppearanceValue,
  serializeAppearanceState
} from "./appearancePicker";

describe("appearancePicker domain", () => {
  it("exposes every agreed category, field limit, and reporter color", () => {
    expect(APPEARANCE_KEYS).toEqual([
      "head",
      "face",
      "top",
      "bottom",
      "shoes",
      "accessory",
      "body",
      "feature"
    ]);
    expect(APPEARANCE_CATEGORIES.map(({ key }) => key)).toEqual(APPEARANCE_KEYS);
    expect(APPEARANCE_LIMITS).toEqual({
      head: 255,
      face: 255,
      top: 255,
      bottom: 255,
      shoes: 255,
      accessory: 1000,
      body: 255,
      feature: 2000
    });
    expect(COLOR_OPTIONS).toEqual([
      "검정",
      "흰색",
      "회색",
      "빨강",
      "주황",
      "노랑",
      "초록",
      "파랑",
      "남색",
      "보라",
      "분홍",
      "갈색",
      "베이지",
      "아이보리",
      "하늘색"
    ]);
  });

  it("uses the exact feature catalogs from the form specification", () => {
    const labels = (key) => getAppearanceCategory(key).options.map(({ label }) => label);

    expect(labels("head")).toEqual(["모자", "긴머리", "짧은머리", "묶은머리", "곱슬머리", "흰머리", "대머리"]);
    expect(labels("face")).toEqual(["둥근 얼굴", "긴 얼굴", "안경", "선글라스", "마스크", "수염", "점·흉터"]);
    expect(labels("top")).toEqual(["티셔츠", "셔츠", "후드티", "니트", "가디건", "조끼", "재킷", "점퍼", "패딩", "코트", "정장"]);
    expect(labels("bottom")).toEqual(["청바지", "면바지", "슬랙스", "반바지", "치마", "레깅스", "트레이닝복", "작업복", "정장바지"]);
    expect(labels("shoes")).toEqual(["운동화", "구두", "로퍼", "샌들", "슬리퍼", "부츠", "장화", "등산화", "안전화", "맨발"]);
    expect(labels("accessory")).toEqual(["백팩", "숄더백", "크로스백", "핸드백", "에코백", "쇼핑백", "우산", "지팡이", "보행보조기", "캐리어"]);
    expect(labels("body")).toEqual(["마른 체형", "보통 체형", "통통한 체형", "건장한 체형", "왜소한 체형", "키가 큼", "키가 작음", "허리가 굽음"]);
    expect(labels("feature")).toEqual(["문신", "흉터", "점", "절뚝거림", "보행 불편", "휠체어 사용", "보청기 착용", "붕대·깁스"]);
    expect(getAppearanceCategory("unknown")).toBeUndefined();
  });

  it("represents a blank value without a stored sentinel", () => {
    expect(parseAppearanceValue("head", "  ")).toEqual({ items: [], note: "" });
    expect(parseAppearanceValue("head", null)).toEqual({ items: [], note: "" });
    expect(serializeAppearanceState({ items: [], note: "" })).toBe("");
  });

  it("round-trips selected features with form and color in canonical order", () => {
    const state = {
      items: [
        { feature: "티셔츠", form: "반팔", color: "파랑" },
        { feature: "패딩", form: "", color: "검정" },
        { feature: "조끼", form: "", color: "" }
      ],
      note: "등 뒤에 숫자 7"
    };
    const serialized = "티셔츠 (반팔, 파랑), 패딩 (검정), 조끼, 등 뒤에 숫자 7";

    expect(serializeAppearanceState(state)).toBe(serialized);
    expect(parseAppearanceValue("top", serialized)).toEqual(state);
    expect(serializeAppearanceState(parseAppearanceValue("top", serialized))).toBe(serialized);
  });

  it.each(APPEARANCE_CATEGORIES)("round-trips every configured $label option", (category) => {
    const state = {
      items: category.options.map((option) => ({
        feature: option.label,
        form: option.forms?.[0] ?? "",
        color: option.allowColor ? COLOR_OPTIONS[0] : ""
      })),
      note: ""
    };
    const serialized = serializeAppearanceState(state);

    expect(parseAppearanceValue(category.key, serialized)).toEqual(state);
    expect(serializeAppearanceState(parseAppearanceValue(category.key, serialized))).toBe(serialized);
  });

  it("keeps an unknown legacy value as a direct-entry note", () => {
    expect(parseAppearanceValue("top", "검은 줄무늬 남방")).toEqual({
      items: [],
      note: "검은 줄무늬 남방"
    });
    expect(parseAppearanceValue("unknown", "기존 원문")).toEqual({ items: [], note: "기존 원문" });
  });

  it("separates configured selections from mixed free-text notes", () => {
    expect(parseAppearanceValue("accessory", "백팩 (빨강), 목에 건 사원증, 우산 (파랑)")).toEqual({
      items: [
        { feature: "백팩", form: "", color: "빨강" },
        { feature: "우산", form: "", color: "파랑" }
      ],
      note: "목에 건 사원증"
    });
  });

  it("does not split commas inside attribute parentheses", () => {
    expect(parseAppearanceValue("bottom", "치마 (긴치마, 베이지), 오른쪽 주머니에 자수")).toEqual({
      items: [{ feature: "치마", form: "긴치마", color: "베이지" }],
      note: "오른쪽 주머니에 자수"
    });
  });

  it("falls back to the original token when an attribute is invalid for that feature", () => {
    expect(parseAppearanceValue("top", "티셔츠 (긴치마, 검정), 패딩 (민소매), 코트 (남색)")).toEqual({
      items: [{ feature: "코트", form: "", color: "남색" }],
      note: "티셔츠 (긴치마, 검정), 패딩 (민소매)"
    });
    expect(parseAppearanceValue("bottom", "청바지 (긴치마), 치마 (긴치마, 베이지)")).toEqual({
      items: [{ feature: "치마", form: "긴치마", color: "베이지" }],
      note: "청바지 (긴치마)"
    });
    expect(parseAppearanceValue("shoes", "맨발 (검정)")).toEqual({ items: [], note: "맨발 (검정)" });
  });

  it("accepts a single valid form or color while rejecting empty and repeated attributes", () => {
    expect(parseAppearanceValue("top", "셔츠 (긴팔), 재킷 (회색)")).toEqual({
      items: [
        { feature: "셔츠", form: "긴팔", color: "" },
        { feature: "재킷", form: "", color: "회색" }
      ],
      note: ""
    });
    expect(parseAppearanceValue("top", "셔츠 (), 티셔츠 (긴팔, 긴팔), 니트 (검정, 검정)")).toEqual({
      items: [],
      note: "셔츠 (), 티셔츠 (긴팔, 긴팔), 니트 (검정, 검정)"
    });
  });

  it("keeps duplicate legacy tokens in the note instead of losing data", () => {
    expect(parseAppearanceValue("head", "모자 (검정), 모자 (흰색), 긴머리, 긴머리")).toEqual({
      items: [
        { feature: "모자", form: "", color: "검정" },
        { feature: "긴머리", form: "", color: "" }
      ],
      note: "모자 (흰색), 긴머리"
    });
    expect(serializeAppearanceState({
      items: [
        { feature: "모자", form: "", color: "검정" },
        { feature: "모자", form: "", color: "흰색" }
      ],
      note: ""
    })).toBe("모자 (검정)");
  });

  it("trims state values and omits the old '안함' selection sentinel", () => {
    expect(serializeAppearanceState({
      items: [{ feature: " 티셔츠 ", form: " 안함 ", color: " 파랑 " }],
      note: "  소매에 로고  "
    })).toBe("티셔츠 (파랑), 소매에 로고");
  });
});
