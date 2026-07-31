import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { fetchAdminCandidatesMock, listCamerasMock, listCasesMock } = vi.hoisted(() => ({
  fetchAdminCandidatesMock: vi.fn(),
  listCamerasMock: vi.fn(),
  listCasesMock: vi.fn()
}));

vi.mock("./candidateApi", () => ({ fetchAdminCandidates: fetchAdminCandidatesMock }));
vi.mock("./cameraApi", () => ({ listCameras: listCamerasMock }));
vi.mock("./caseApi", () => ({ listCases: listCasesMock }));

import { getCases, getChartData, getDashboardSummary } from "./dashboardApi";

const paged = (data = [], totalElements = data.length, totalPages = 1) => ({
  data,
  meta: { page: 0, size: 100, totalElements, totalPages, sort: "reportedAt,desc" }
});

describe("dashboardApi", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-31T03:00:00Z"));
    listCasesMock.mockReset();
    listCamerasMock.mockReset();
    fetchAdminCandidatesMock.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns DB counts for dashboard summary cards", async () => {
    listCasesMock.mockImplementation(async (params) => {
      if (params.status === "SEARCHING") return paged([], 7);
      if (params.status === "CANDIDATE_FOUND") return paged([], 3);
      if (params.reportedFrom) return paged([], 2);
      return paged([], 41);
    });
    listCamerasMock.mockResolvedValue(paged([], 18));

    await expect(getDashboardSummary()).resolves.toEqual([
      { id: "total", title: "전체 사건 수", value: 41, delta: null },
      { id: "searching", title: "탐색 중 사건 수", value: 7, delta: null },
      { id: "candidate", title: "후보 발견 사건 수", value: 3, delta: null },
      { id: "today", title: "오늘 접수 신고 수", value: 2, delta: null },
      { id: "cctv", title: "운영 중 CCTV 수", value: 18, delta: null }
    ]);

    expect(listCamerasMock).toHaveBeenCalledWith({ status: "ONLINE", page: 0, size: 1 });
  });

  it("maps the server-paged case list to dashboard rows", async () => {
    listCasesMock.mockResolvedValue(paged([
      {
        id: 12,
        caseNumber: "EFU-12",
        status: "SEARCHING",
        missingName: "Missing",
        gender: "UNKNOWN",
        birthYear: 2010,
        photoUrl: null,
        lastSeenTime: "2026-07-30T12:00:00Z",
        lastSeenAddress: "Seoul",
        reportedAt: "2026-07-31T00:00:00Z",
        updatedAt: "2026-07-31T01:00:00Z"
      }
    ], 101, 11));

    await expect(getCases({ page: 2, size: 10 })).resolves.toMatchObject({
      data: [{ id: 12, caseNumber: "EFU-12", status: "searching" }],
      meta: { totalElements: 101, totalPages: 11 }
    });
    expect(listCasesMock).toHaveBeenCalledWith({ page: 2, size: 10, sort: "reportedAt,desc" });
  });

  it("rejects malformed paged responses instead of showing zero rows", async () => {
    listCasesMock.mockResolvedValue({ data: [], meta: {} });

    await expect(getCases()).rejects.toMatchObject({ code: "INVALID_API_RESPONSE" });
  });

  it("builds chart buckets from report and candidate timestamps", async () => {
    listCasesMock.mockResolvedValue(paged([
      { reportedAt: "2026-07-31T02:00:00Z" }
    ], 1));
    fetchAdminCandidatesMock.mockResolvedValue({
      rows: [{ lastDetectedAt: "2026-07-31T02:30:00Z" }],
      meta: { page: 0, size: 100, totalElements: 1, totalPages: 1, sort: "lastDetectedAt,asc" }
    });

    const chart = await getChartData("7d");

    expect(chart).toHaveLength(7);
    expect(chart.at(-1)).toMatchObject({ date: "07-31", reports: 1, candidates: 1 });
    expect(listCasesMock).toHaveBeenCalledWith(expect.objectContaining({
      reportedFrom: "2026-07-25T00:00:00+09:00",
      reportedTo: "2026-08-01T00:00:00+09:00",
      page: 0,
      size: 100,
      sort: "reportedAt,asc"
    }));
    expect(fetchAdminCandidatesMock).toHaveBeenCalledWith(expect.objectContaining({
      detectedFrom: "2026-07-25T00:00:00+09:00",
      detectedTo: "2026-08-01T00:00:00+09:00"
    }));
  });

  it("merges chart rows from bounded additional pages", async () => {
    listCasesMock.mockImplementation(async (params) => {
      if (!params.reportedFrom) return paged([], 0, 0);
      return paged(
        params.page === 0 ? [{ reportedAt: "2026-07-30T02:00:00Z" }] : [{ reportedAt: "2026-07-31T02:00:00Z" }],
        2,
        2
      );
    });
    fetchAdminCandidatesMock.mockImplementation(async (params) => ({
      rows: params.page === 0 ? [{ lastDetectedAt: "2026-07-30T02:30:00Z" }] : [{ lastDetectedAt: "2026-07-31T02:30:00Z" }],
      meta: { page: params.page, size: 100, totalElements: 2, totalPages: 2, sort: "lastDetectedAt,asc" }
    }));

    const chart = await getChartData("7d");

    expect(chart.find((item) => item.date === "07-30")).toMatchObject({ reports: 1, candidates: 1 });
    expect(chart.find((item) => item.date === "07-31")).toMatchObject({ reports: 1, candidates: 1 });
    expect(listCasesMock).toHaveBeenCalledWith(expect.objectContaining({ page: 1, size: 100 }));
    expect(fetchAdminCandidatesMock).toHaveBeenCalledWith(expect.objectContaining({ page: 1, size: 100 }));
  });
});
