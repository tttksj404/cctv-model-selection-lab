export const GENDER_OPTIONS = Object.freeze([
  { value: "person", label: "사람" },
  { value: "man", label: "남성" },
  { value: "woman", label: "여성" }
]);

export const COLOR_OPTIONS = Object.freeze([
  { value: "black", label: "검정" },
  { value: "blue", label: "파랑" },
  { value: "brown", label: "갈색" },
  { value: "green", label: "초록" },
  { value: "gray", label: "회색" },
  { value: "orange", label: "주황" },
  { value: "pink", label: "분홍" },
  { value: "purple", label: "보라" },
  { value: "red", label: "빨강" },
  { value: "white", label: "흰색" },
  { value: "yellow", label: "노랑" }
]);

export const SLEEVE_OPTIONS = Object.freeze([
  { value: "short sleeve", label: "반팔" },
  { value: "long sleeve", label: "긴팔" }
]);

const GENDERS = new Set(GENDER_OPTIONS.map(({ value }) => value));
const COLORS = new Set(COLOR_OPTIONS.map(({ value }) => value));
const SLEEVES = new Set(SLEEVE_OPTIONS.map(({ value }) => value));
const CANONICAL_PATTERN = new RegExp(
  `^a (${[...GENDERS].join("|")}) wearing a (${[...COLORS].join("|")}) (${[...SLEEVES].join("|")}) top and (${[...COLORS].join("|")}) pants$`,
  "i"
);

export function emptyDescriptor() {
  return { gender: "person", upperColor: "", sleeve: "", lowerColor: "" };
}

export function buildCanonicalPrompt(descriptor = {}) {
  const gender = String(descriptor.gender ?? "").trim().toLowerCase();
  const upperColor = String(descriptor.upperColor ?? "").trim().toLowerCase();
  const sleeve = String(descriptor.sleeve ?? "").trim().toLowerCase();
  const lowerColor = String(descriptor.lowerColor ?? "").trim().toLowerCase();

  if (
    !GENDERS.has(gender)
      || !COLORS.has(upperColor)
      || !SLEEVES.has(sleeve)
      || !COLORS.has(lowerColor)
  ) return "";

  return `a ${gender} wearing a ${upperColor} ${sleeve} top and ${lowerColor} pants`;
}

export function parseCanonicalPrompt(prompt) {
  const match = String(prompt ?? "").trim().match(CANONICAL_PATTERN);
  if (!match) return null;
  return {
    gender: match[1].toLowerCase(),
    upperColor: match[2].toLowerCase(),
    sleeve: match[3].toLowerCase(),
    lowerColor: match[4].toLowerCase()
  };
}

export function toLocalDateTimeInput(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (part) => String(part).padStart(2, "0");
  const milliseconds = date.getMilliseconds();
  const fraction = milliseconds ? `.${String(milliseconds).padStart(3, "0")}` : "";
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
    + `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}${fraction}`;
}

function toApiDateTime(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

export function validateSearchConditionForm(form) {
  if (!buildCanonicalPrompt(form.subject)) {
    return "성별, 상의 색, 소매 길이와 하의 색을 모두 선택해 주세요.";
  }
  if (form.exclusionEnabled && !buildCanonicalPrompt(form.exclusion)) {
    return "제외 조건을 사용하려면 제외 대상의 모든 항목을 선택해 주세요.";
  }

  const hasStart = Boolean(form.searchStart);
  const hasEnd = Boolean(form.searchEnd);
  if (hasStart !== hasEnd) {
    return "탐색 시작과 종료 일시는 함께 입력하거나 모두 비워 주세요.";
  }
  if (hasStart) {
    const start = new Date(form.searchStart);
    const end = new Date(form.searchEnd);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
      return "탐색 기간을 올바른 일시로 입력해 주세요.";
    }
    if (end.getTime() < start.getTime()) {
      return "탐색 종료 일시는 시작 일시보다 빠를 수 없습니다.";
    }
  }
  return "";
}

export function buildSearchConditionPayload(form) {
  const validationError = validateSearchConditionForm(form);
  if (validationError) throw new TypeError(validationError);

  return {
    prompt: buildCanonicalPrompt(form.subject),
    exclusionPrompt: form.exclusionEnabled ? buildCanonicalPrompt(form.exclusion) : null,
    searchStart: toApiDateTime(form.searchStart),
    searchEnd: toApiDateTime(form.searchEnd),
    searchArea: String(form.searchArea ?? "").trim() || null
  };
}
