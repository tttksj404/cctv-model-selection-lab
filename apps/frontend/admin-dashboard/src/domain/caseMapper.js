const BACKEND_TO_UI_STATUS = Object.freeze({
  RECEIVED: "received",
  SEARCHING: "searching",
  CANDIDATE_FOUND: "candidate_found",
  FIELD_SEARCH: "field_search",
  CLOSED: "closed"
});

const UI_TO_BACKEND_STATUS = Object.freeze(
  Object.fromEntries(Object.entries(BACKEND_TO_UI_STATUS).map(([backend, ui]) => [ui, backend]))
);

const BACKEND_TO_UI_GENDER = Object.freeze({
  MALE: "남",
  FEMALE: "여",
  UNKNOWN: "확인 필요"
});

const UI_TO_BACKEND_GENDER = Object.freeze({
  남: "MALE",
  여: "FEMALE",
  "확인 필요": "UNKNOWN"
});

const KST_FORMATTER = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Asia/Seoul",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23"
});

const KST_YEAR_FORMATTER = new Intl.DateTimeFormat("en", {
  timeZone: "Asia/Seoul",
  year: "numeric"
});

const APPEARANCE_FIELDS = Object.freeze([
  ["head", "hair"],
  ["face", "face"],
  ["top", "upperClothing"],
  ["bottom", "lowerClothing"],
  ["shoes", "shoes"],
  ["accessory", "belongings"],
  ["body", "bodyType"],
  ["feature", "distinctiveFeatures"]
]);

function kstDateTimeParts(value) {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return null;

  const parts = Object.fromEntries(
    KST_FORMATTER.formatToParts(date)
      .filter(({ type }) => type !== "literal")
      .map(({ type, value: partValue }) => [type, partValue])
  );
  return {
    date: `${parts.year}-${parts.month}-${parts.day}`,
    time: `${parts.hour}:${parts.minute}`
  };
}

function currentKstYear() {
  return Number(KST_YEAR_FORMATTER.format(new Date()));
}

function calculateAge(birthYear) {
  const year = Number(birthYear);
  return Number.isInteger(year) && year > 0 ? currentKstYear() - year + 1 : "";
}

function toUiGender(gender) {
  if (!gender) return "확인 필요";
  return BACKEND_TO_UI_GENDER[gender] ?? gender;
}

function toBackendGender(gender) {
  if (!gender) return "UNKNOWN";
  if (BACKEND_TO_UI_GENDER[gender]) return gender;
  return UI_TO_BACKEND_GENDER[gender] ?? "UNKNOWN";
}

function cleanText(value) {
  return typeof value === "string" ? value.trim() : value;
}

function optionalText(value) {
  const cleaned = cleanText(value);
  return cleaned === "" || cleaned === undefined ? null : cleaned;
}

function numericOrNull(value) {
  if (value === "" || value === null || value === undefined) return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function formDateTimeToKstOffset(date, time) {
  if (!date || !time) return null;
  const normalizedTime = /^\d{2}:\d{2}$/.test(time) ? `${time}:00` : time;
  return `${date}T${normalizedTime}+09:00`;
}

function reporterSummary(reporter = {}) {
  const relation = reporter.relation ? `(${reporter.relation})` : "";
  const identity = `${reporter.name ?? ""}${relation}`;
  return [identity, reporter.phone].filter(Boolean).join(" / ");
}

function appearanceSummary(appearance = {}) {
  return APPEARANCE_FIELDS
    .map(([, backendKey]) => appearance[backendKey])
    .filter((value) => typeof value === "string" && value.trim())
    .join(", ");
}

export function toBackendStatus(status) {
  if (BACKEND_TO_UI_STATUS[status]) return status;
  const backendStatus = UI_TO_BACKEND_STATUS[status];
  if (!backendStatus) throw new TypeError(`지원하지 않는 사건 상태입니다: ${status}`);
  return backendStatus;
}

export function toUiStatus(status) {
  if (UI_TO_BACKEND_STATUS[status]) return status;
  return BACKEND_TO_UI_STATUS[status] ?? String(status ?? "").toLowerCase();
}

export function formatKstDateTime(value) {
  const parts = kstDateTimeParts(value);
  return parts ? `${parts.date} ${parts.time}` : "";
}

export function mapCaseListItem(source) {
  const status = toUiStatus(source.status);
  const gender = toUiGender(source.gender);
  return {
    id: source.id,
    caseNumber: source.caseNumber,
    name: source.missingName,
    missingName: source.missingName,
    status,
    statusCode: source.status,
    gender,
    genderCode: source.gender,
    birthYear: source.birthYear,
    age: calculateAge(source.birthYear),
    photo: source.photoUrl ? "기준 사진" : "사진 없음",
    photoUrl: source.photoUrl ?? null,
    lastSeenAt: formatKstDateTime(source.lastSeenTime),
    lastSeenTimeIso: source.lastSeenTime,
    lastSeenLocation: source.lastSeenAddress,
    lastSeenAddress: source.lastSeenAddress,
    reportedAt: formatKstDateTime(source.reportedAt),
    reportedAtIso: source.reportedAt,
    updatedAt: formatKstDateTime(source.updatedAt),
    updatedAtIso: source.updatedAt,
    assignee: "-"
  };
}

export function mapCaseDetail(source) {
  const base = mapCaseListItem(source);
  const reporterInfo = source.reporter ?? {};
  const appearanceInfo = source.appearance ?? {};
  return {
    ...base,
    reporter: reporterSummary(reporterInfo),
    reporterInfo,
    appearance: appearanceSummary(appearanceInfo),
    appearanceInfo,
    reportContent: source.reportContent,
    lastSeenLat: source.lastSeenLat ?? null,
    lastSeenLng: source.lastSeenLng ?? null,
    closedAt: formatKstDateTime(source.closedAt),
    closedAtIso: source.closedAt,
    raw: source
  };
}

export function caseDetailToForm(source) {
  const reporter = source.reporter ?? {};
  const appearance = source.appearance ?? {};
  const lastSeen = kstDateTimeParts(source.lastSeenTime);
  const birthYear = source.birthYear == null ? "" : String(source.birthYear);

  return {
    reporterName: reporter.name ?? "",
    reporterPhone: reporter.phone ?? "",
    relation: reporter.relation ?? "",
    name: source.missingName ?? "",
    gender: toUiGender(source.gender),
    birthYear,
    age: birthYear ? String(calculateAge(source.birthYear)) : "",
    head: appearance.hair ?? "",
    face: appearance.face ?? "",
    top: appearance.upperClothing ?? "",
    bottom: appearance.lowerClothing ?? "",
    shoes: appearance.shoes ?? "",
    accessory: appearance.belongings ?? "",
    body: appearance.bodyType ?? "",
    feature: appearance.distinctiveFeatures ?? "",
    lastSeenDate: lastSeen?.date ?? "",
    lastSeenTime: lastSeen?.time ?? "",
    lastSeenLocation: source.lastSeenAddress ?? "",
    story: source.reportContent ?? ""
  };
}

export function buildCreateCasePayload(form) {
  return {
    reporter: {
      name: cleanText(form.reporterName),
      phone: cleanText(form.reporterPhone),
      relation: optionalText(form.relation)
    },
    reportContent: cleanText(form.story),
    missingName: cleanText(form.name),
    gender: toBackendGender(form.gender),
    birthYear: numericOrNull(form.birthYear),
    appearance: Object.fromEntries(
      APPEARANCE_FIELDS.map(([formKey, backendKey]) => [backendKey, optionalText(form[formKey])])
    ),
    lastSeenTime: formDateTimeToKstOffset(form.lastSeenDate, form.lastSeenTime),
    lastSeenLat: null,
    lastSeenLng: null,
    lastSeenAddress: cleanText(form.lastSeenLocation)
  };
}

export function buildCaseUpdatePatch(initialForm, currentForm) {
  const patch = {};
  const reporter = {};
  const appearance = {};

  const reporterFields = [
    ["reporterName", "name", cleanText],
    ["reporterPhone", "phone", cleanText],
    ["relation", "relation", optionalText]
  ];
  for (const [formKey, backendKey, normalize] of reporterFields) {
    const initial = normalize(initialForm[formKey]);
    const current = normalize(currentForm[formKey]);
    if (current !== initial) reporter[backendKey] = current;
  }
  if (Object.keys(reporter).length) patch.reporter = reporter;

  const scalarFields = [
    ["story", "reportContent", cleanText],
    ["name", "missingName", cleanText],
    ["gender", "gender", toBackendGender],
    ["birthYear", "birthYear", numericOrNull]
  ];
  for (const [formKey, backendKey, normalize] of scalarFields) {
    const initial = normalize(initialForm[formKey]);
    const current = normalize(currentForm[formKey]);
    if (current !== initial) patch[backendKey] = current;
  }

  for (const [formKey, backendKey] of APPEARANCE_FIELDS) {
    const initial = optionalText(initialForm[formKey]);
    const current = optionalText(currentForm[formKey]);
    if (current !== initial) appearance[backendKey] = current;
  }
  if (Object.keys(appearance).length) patch.appearance = appearance;

  const initialLastSeenTime = formDateTimeToKstOffset(
    initialForm.lastSeenDate,
    initialForm.lastSeenTime
  );
  const currentLastSeenTime = formDateTimeToKstOffset(
    currentForm.lastSeenDate,
    currentForm.lastSeenTime
  );
  if (currentLastSeenTime !== initialLastSeenTime) patch.lastSeenTime = currentLastSeenTime;

  const initialAddress = cleanText(initialForm.lastSeenLocation);
  const currentAddress = cleanText(currentForm.lastSeenLocation);
  if (currentAddress !== initialAddress) {
    patch.lastSeenAddress = currentAddress;
    // The form edits a textual address without geocoding. Clear stale coordinates atomically.
    patch.lastSeenLat = null;
    patch.lastSeenLng = null;
  }

  return patch;
}
