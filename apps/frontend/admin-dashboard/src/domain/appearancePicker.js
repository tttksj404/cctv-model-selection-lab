export const APPEARANCE_KEYS = Object.freeze([
  "head",
  "face",
  "top",
  "bottom",
  "shoes",
  "accessory",
  "body",
  "feature"
]);

export const APPEARANCE_LIMITS = Object.freeze({
  head: 255,
  face: 255,
  top: 255,
  bottom: 255,
  shoes: 255,
  accessory: 1000,
  body: 255,
  feature: 2000
});

export const COLOR_OPTIONS = Object.freeze([
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

const FULL_SLEEVE_OPTIONS = Object.freeze(["긴팔", "반팔", "민소매"]);
const SLEEVE_OPTIONS = Object.freeze(["긴팔", "반팔"]);
const PANTS_LENGTH_OPTIONS = Object.freeze(["긴바지", "7부바지"]);
const SKIRT_LENGTH_OPTIONS = Object.freeze(["긴치마", "짧은치마"]);

export const APPEARANCE_CATEGORIES = Object.freeze([
  {
    key: "head",
    label: "머리",
    options: [
      { label: "모자", allowColor: true },
      { label: "긴머리", allowColor: true },
      { label: "짧은머리", allowColor: true },
      { label: "묶은머리", allowColor: true },
      { label: "곱슬머리", allowColor: true },
      { label: "흰머리" },
      { label: "대머리" }
    ]
  },
  {
    key: "face",
    label: "얼굴",
    options: [
      { label: "둥근 얼굴" },
      { label: "긴 얼굴" },
      { label: "안경", allowColor: true },
      { label: "선글라스", allowColor: true },
      { label: "마스크", allowColor: true },
      { label: "수염", allowColor: true },
      { label: "점·흉터" }
    ]
  },
  {
    key: "top",
    label: "상의",
    options: [
      { label: "티셔츠", forms: FULL_SLEEVE_OPTIONS, allowColor: true },
      { label: "셔츠", forms: FULL_SLEEVE_OPTIONS, allowColor: true },
      { label: "후드티", forms: SLEEVE_OPTIONS, allowColor: true },
      { label: "니트", forms: FULL_SLEEVE_OPTIONS, allowColor: true },
      { label: "가디건", forms: SLEEVE_OPTIONS, allowColor: true },
      { label: "조끼", allowColor: true },
      { label: "재킷", allowColor: true },
      { label: "점퍼", allowColor: true },
      { label: "패딩", allowColor: true },
      { label: "코트", allowColor: true },
      { label: "정장", allowColor: true }
    ]
  },
  {
    key: "bottom",
    label: "하의",
    options: [
      { label: "청바지", forms: PANTS_LENGTH_OPTIONS, allowColor: true },
      { label: "면바지", forms: PANTS_LENGTH_OPTIONS, allowColor: true },
      { label: "슬랙스", forms: PANTS_LENGTH_OPTIONS, allowColor: true },
      { label: "반바지", allowColor: true },
      { label: "치마", forms: SKIRT_LENGTH_OPTIONS, allowColor: true },
      { label: "레깅스", forms: PANTS_LENGTH_OPTIONS, allowColor: true },
      { label: "트레이닝복", forms: PANTS_LENGTH_OPTIONS, allowColor: true },
      { label: "작업복", forms: PANTS_LENGTH_OPTIONS, allowColor: true },
      { label: "정장바지", forms: PANTS_LENGTH_OPTIONS, allowColor: true }
    ]
  },
  {
    key: "shoes",
    label: "신발",
    options: [
      { label: "운동화", allowColor: true },
      { label: "구두", allowColor: true },
      { label: "로퍼", allowColor: true },
      { label: "샌들", allowColor: true },
      { label: "슬리퍼", allowColor: true },
      { label: "부츠", allowColor: true },
      { label: "장화", allowColor: true },
      { label: "등산화", allowColor: true },
      { label: "안전화", allowColor: true },
      { label: "맨발" }
    ]
  },
  {
    key: "accessory",
    label: "소지품",
    options: [
      { label: "백팩", allowColor: true },
      { label: "숄더백", allowColor: true },
      { label: "크로스백", allowColor: true },
      { label: "핸드백", allowColor: true },
      { label: "에코백", allowColor: true },
      { label: "쇼핑백", allowColor: true },
      { label: "우산", allowColor: true },
      { label: "지팡이", allowColor: true },
      { label: "보행보조기", allowColor: true },
      { label: "캐리어", allowColor: true }
    ]
  },
  {
    key: "body",
    label: "체형",
    options: [
      { label: "마른 체형" },
      { label: "보통 체형" },
      { label: "통통한 체형" },
      { label: "건장한 체형" },
      { label: "왜소한 체형" },
      { label: "키가 큼" },
      { label: "키가 작음" },
      { label: "허리가 굽음" }
    ]
  },
  {
    key: "feature",
    label: "기타 특징",
    options: [
      { label: "문신" },
      { label: "흉터" },
      { label: "점" },
      { label: "절뚝거림" },
      { label: "보행 불편" },
      { label: "휠체어 사용" },
      { label: "보청기 착용" },
      { label: "붕대·깁스" }
    ]
  }
]);

const COLOR_SET = new Set(COLOR_OPTIONS);

export function getAppearanceCategory(key) {
  return APPEARANCE_CATEGORIES.find((category) => category.key === key);
}

function splitTopLevel(value) {
  const tokens = [];
  let token = "";
  let depth = 0;

  for (const character of value) {
    if (character === "(") depth += 1;
    if (character === ")" && depth > 0) depth -= 1;

    if (character === "," && depth === 0) {
      tokens.push(token.trim());
      token = "";
      continue;
    }

    token += character;
  }

  tokens.push(token.trim());
  return tokens.filter(Boolean);
}

function parseKnownItem(token, option) {
  if (token === option.label) {
    return { feature: option.label, form: "", color: "" };
  }

  const escapedLabel = option.label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = token.match(new RegExp(`^${escapedLabel}\\s*\\(([^()]*)\\)$`));
  if (!match) return null;

  const attributes = match[1].split(",").map((attribute) => attribute.trim());
  if (!attributes.length || attributes.some((attribute) => !attribute) || attributes.length > 2) {
    return null;
  }

  let form = "";
  let color = "";
  const forms = option.forms ?? [];

  for (const attribute of attributes) {
    if (!form && forms.includes(attribute)) {
      form = attribute;
      continue;
    }
    if (!color && option.allowColor && COLOR_SET.has(attribute)) {
      color = attribute;
      continue;
    }
    return null;
  }

  return { feature: option.label, form, color };
}

export function parseAppearanceValue(key, value) {
  const category = getAppearanceCategory(key);
  const source = String(value ?? "").trim();
  if (!source) return { items: [], note: "" };
  if (!category) return { items: [], note: source };

  const optionsByLabel = new Map(category.options.map((option) => [option.label, option]));
  const items = [];
  const notes = [];
  const seenFeatures = new Set();

  for (const token of splitTopLevel(source)) {
    const feature = token.split("(", 1)[0].trim();
    const option = optionsByLabel.get(feature);
    const item = option ? parseKnownItem(token, option) : null;

    if (!item) {
      notes.push(token);
      continue;
    }

    if (seenFeatures.has(item.feature)) {
      notes.push(token);
      continue;
    }
    seenFeatures.add(item.feature);
    items.push(item);
  }

  return { items, note: notes.join(", ") };
}

export function serializeAppearanceState(state) {
  const values = [];
  const seenFeatures = new Set();

  for (const item of Array.isArray(state?.items) ? state.items : []) {
    const feature = String(item?.feature ?? "").trim();
    if (!feature || seenFeatures.has(feature)) continue;

    seenFeatures.add(feature);
    const attributes = [item?.form, item?.color]
      .map((attribute) => String(attribute ?? "").trim())
      .filter((attribute) => attribute && attribute !== "안함");
    values.push(attributes.length ? `${feature} (${attributes.join(", ")})` : feature);
  }

  const note = String(state?.note ?? "").trim();
  if (note) values.push(note);
  return values.join(", ");
}
