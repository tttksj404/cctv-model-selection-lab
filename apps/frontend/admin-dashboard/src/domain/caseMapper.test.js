import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  buildCaseUpdatePatch,
  buildCreateCasePayload,
  caseDetailToForm,
  formatKstDateTime,
  mapCaseDetail,
  mapCaseListItem,
  toBackendStatus,
  toUiStatus
} from "./caseMapper";

const rawDetail = () => ({
  id: 17,
  caseNumber: "EFU-0123456789ABCDEFGHJKMNPQRS",
  status: "CANDIDATE_FOUND",
  reporter: {
    id: 9,
    name: "홍길동",
    phone: "01012345678",
    email: null,
    relation: "보호자"
  },
  reportContent: "실종 경위",
  missingName: "김민수",
  gender: "MALE",
  birthYear: 1952,
  appearance: {
    hair: "짧은 머리",
    face: "안경",
    upperClothing: "검은 셔츠",
    lowerClothing: "회색 바지",
    shoes: "흰 운동화",
    belongings: "지팡이",
    bodyType: "마른 체형",
    distinctiveFeatures: "오른쪽 다리를 절음"
  },
  photoUrl: "https://storage.example/photo.jpg",
  lastSeenTime: "2026-07-20T00:10:00Z",
  lastSeenLat: 37.5,
  lastSeenLng: 127.03,
  lastSeenAddress: "서울 강남구",
  reportedAt: "2026-07-20T01:30:00Z",
  closedAt: null,
  updatedAt: "2026-07-20T02:00:00Z"
});

describe("caseMapper", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-30T00:00:00Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("백엔드 상태와 UI 상태를 양방향 변환한다", () => {
    expect(toUiStatus("RECEIVED")).toBe("received");
    expect(toUiStatus("CANDIDATE_FOUND")).toBe("candidate_found");
    expect(toUiStatus("FIELD_SEARCH")).toBe("field_search");
    expect(toBackendStatus("searching")).toBe("SEARCHING");
    expect(toBackendStatus("field_search")).toBe("FIELD_SEARCH");
    expect(() => toBackendStatus("preparing")).toThrow(TypeError);
  });

  it("서버 Instant를 실행 환경과 무관하게 KST로 표시한다", () => {
    expect(formatKstDateTime("2026-07-20T00:10:00Z")).toBe("2026-07-20 09:10");
    expect(formatKstDateTime("2026-07-20T23:30:00Z")).toBe("2026-07-21 08:30");
    expect(formatKstDateTime(null)).toBe("");
  });

  it("목록 응답을 기존 사건 테이블용 UI 모델로 변환한다", () => {
    const mapped = mapCaseListItem(rawDetail());

    expect(mapped).toMatchObject({
      id: 17,
      name: "김민수",
      gender: "남",
      age: 75,
      status: "candidate_found",
      photo: "기준 사진",
      lastSeenAt: "2026-07-20 09:10",
      lastSeenLocation: "서울 강남구",
      reportedAt: "2026-07-20 10:30",
      assignee: "-"
    });
  });

  it("상세 응답에 신고자·인상착의 표시 문자열과 원본 객체를 함께 제공한다", () => {
    const mapped = mapCaseDetail(rawDetail());

    expect(mapped.reporter).toBe("홍길동(보호자) / 01012345678");
    expect(mapped.appearance).toContain("짧은 머리");
    expect(mapped.appearance).toContain("오른쪽 다리를 절음");
    expect(mapped.reporterInfo.name).toBe("홍길동");
    expect(mapped.appearanceInfo.upperClothing).toBe("검은 셔츠");
    expect(mapped.lastSeenLat).toBe(37.5);
  });

  it("상세 응답을 기존 수정 폼 키와 KST 날짜·시간으로 변환한다", () => {
    expect(caseDetailToForm(rawDetail())).toEqual({
      reporterName: "홍길동",
      reporterPhone: "01012345678",
      relation: "보호자",
      name: "김민수",
      gender: "남",
      birthYear: "1952",
      age: "75",
      head: "짧은 머리",
      face: "안경",
      top: "검은 셔츠",
      bottom: "회색 바지",
      shoes: "흰 운동화",
      accessory: "지팡이",
      body: "마른 체형",
      feature: "오른쪽 다리를 절음",
      lastSeenDate: "2026-07-20",
      lastSeenTime: "09:10",
      lastSeenLocation: "서울 강남구",
      story: "실종 경위"
    });
  });

  it("등록 폼을 백엔드 성별·인상착의·KST offset 요청으로 변환한다", () => {
    const form = caseDetailToForm(rawDetail());
    form.gender = "여";
    form.relation = "  가족  ";

    expect(buildCreateCasePayload(form)).toEqual({
      reporter: {
        name: "홍길동",
        phone: "01012345678",
        relation: "가족"
      },
      reportContent: "실종 경위",
      missingName: "김민수",
      gender: "FEMALE",
      birthYear: 1952,
      appearance: {
        hair: "짧은 머리",
        face: "안경",
        upperClothing: "검은 셔츠",
        lowerClothing: "회색 바지",
        shoes: "흰 운동화",
        belongings: "지팡이",
        bodyType: "마른 체형",
        distinctiveFeatures: "오른쪽 다리를 절음"
      },
      lastSeenTime: "2026-07-20T09:10:00+09:00",
      lastSeenLat: null,
      lastSeenLng: null,
      lastSeenAddress: "서울 강남구"
    });
  });

  it("수정 요청에는 실제로 바뀐 필드만 중첩 PATCH로 포함한다", () => {
    const initial = caseDetailToForm(rawDetail());
    const current = { ...initial, reporterPhone: "010-9999-8888", top: "파란 셔츠" };

    expect(buildCaseUpdatePatch(initial, current)).toEqual({
      reporter: { phone: "010-9999-8888" },
      appearance: { upperClothing: "파란 셔츠" }
    });
    expect(buildCaseUpdatePatch(initial, { ...initial })).toEqual({});
  });

  it("주소를 텍스트로 변경하면 기존 좌표가 남지 않도록 둘 다 null 처리한다", () => {
    const initial = caseDetailToForm(rawDetail());
    const current = { ...initial, lastSeenLocation: "서울 송파구" };

    expect(buildCaseUpdatePatch(initial, current)).toEqual({
      lastSeenAddress: "서울 송파구",
      lastSeenLat: null,
      lastSeenLng: null
    });
  });

  it("날짜·성별·출생 연도 변경도 백엔드 형식으로만 PATCH한다", () => {
    const initial = caseDetailToForm(rawDetail());
    const current = {
      ...initial,
      gender: "확인 필요",
      birthYear: "",
      lastSeenDate: "2026-07-21",
      lastSeenTime: "08:30"
    };

    expect(buildCaseUpdatePatch(initial, current)).toEqual({
      gender: "UNKNOWN",
      birthYear: null,
      lastSeenTime: "2026-07-21T08:30:00+09:00"
    });
  });
});
