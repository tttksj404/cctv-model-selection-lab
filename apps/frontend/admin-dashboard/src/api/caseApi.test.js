import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  closeCase,
  createCase,
  deleteCasePhoto,
  getCase,
  listCases,
  putCasePhoto,
  updateCase,
  updateCaseStatus
} from "./caseApi";
import { apiClient, setUnauthorizedHandler } from "./httpClient";

const originalAdapter = apiClient.defaults.adapter;

const response = (config, data, status = 200) => ({
  config,
  data,
  headers: {},
  request: {},
  status,
  statusText: status === 204 ? "No Content" : "OK"
});

const setCsrfCookie = () => {
  document.cookie = "XSRF-TOKEN=case-api-token; path=/";
};

const clearCsrfCookie = () => {
  document.cookie = "XSRF-TOKEN=; Max-Age=0; path=/";
};

describe("caseApi", () => {
  beforeEach(() => {
    clearCsrfCookie();
    setCsrfCookie();
    setUnauthorizedHandler(null);
  });

  afterEach(() => {
    apiClient.defaults.adapter = originalAdapter;
    clearCsrfCookie();
    setUnauthorizedHandler(null);
  });

  it("사건 목록의 data와 meta를 반환하고 검색 조건을 전달한다", async () => {
    const adapter = vi.fn(async (config) => response(config, {
      timestamp: "2026-07-30T00:00:00Z",
      data: [{ id: 1, caseNumber: "EFU-1" }],
      meta: { page: 0, size: 20, totalElements: 1, totalPages: 1, sort: "reportedAt,desc" }
    }));
    apiClient.defaults.adapter = adapter;

    await expect(listCases({ status: "RECEIVED", page: 2, size: 10 })).resolves.toEqual({
      data: [{ id: 1, caseNumber: "EFU-1" }],
      meta: { page: 0, size: 20, totalElements: 1, totalPages: 1, sort: "reportedAt,desc" }
    });
    expect(adapter.mock.calls[0][0]).toMatchObject({
      method: "get",
      url: "/admin/cases",
      params: { status: "RECEIVED", page: 2, size: 10 }
    });
  });

  it("상세 조회와 JSON 생성·부분 수정을 공통 응답에서 해제한다", async () => {
    const adapter = vi.fn(async (config) => {
      const data = config.method === "get"
        ? { id: 17, missingName: "김민수" }
        : config.method === "post"
          ? { id: 17, status: "RECEIVED" }
          : { id: 17, missingName: "김민준" };
      return response(config, { timestamp: "2026-07-30T00:00:00Z", data });
    });
    apiClient.defaults.adapter = adapter;

    await expect(getCase(17)).resolves.toMatchObject({ id: 17, missingName: "김민수" });
    await expect(createCase({ missingName: "김민수" })).resolves.toMatchObject({
      id: 17,
      status: "RECEIVED"
    });
    await expect(updateCase(17, { missingName: "김민준" })).resolves.toMatchObject({
      id: 17,
      missingName: "김민준"
    });

    expect(adapter.mock.calls.map(([config]) => `${config.method} ${config.url}`)).toEqual([
      "get /admin/cases/17",
      "post /admin/cases",
      "patch /admin/cases/17"
    ]);
    expect(JSON.parse(adapter.mock.calls[1][0].data)).toEqual({ missingName: "김민수" });
    expect(JSON.parse(adapter.mock.calls[2][0].data)).toEqual({ missingName: "김민준" });
  });

  it("사진은 Content-Type을 직접 지정하지 않고 photo 파트의 FormData로 전송한다", async () => {
    const put = vi.spyOn(apiClient, "put").mockImplementation(async (url, body, config) => response(
      { method: "put", url, data: body, ...config },
      {
        timestamp: "2026-07-30T00:00:00Z",
        data: { photoUrl: "https://storage.example/photo.jpg" }
      }
    ));
    const photo = new File([new Uint8Array([0xff, 0xd8, 0xff])], "person.jpg", {
      type: "image/jpeg"
    });

    await expect(putCasePhoto(17, photo)).resolves.toEqual({
      photoUrl: "https://storage.example/photo.jpg"
    });

    expect(put).toHaveBeenCalledOnce();
    expect(put.mock.calls[0]).toHaveLength(2);
    expect(put.mock.calls[0][0]).toBe("/admin/cases/17/photo");
    expect(put.mock.calls[0][1]).toBeInstanceOf(FormData);
    expect(put.mock.calls[0][1].get("photo")).toBe(photo);
  });

  it("사진 삭제의 204 응답을 void로 반환한다", async () => {
    const adapter = vi.fn(async (config) => response(config, "", 204));
    apiClient.defaults.adapter = adapter;

    await expect(deleteCasePhoto(17)).resolves.toBeUndefined();
    expect(adapter).toHaveBeenCalledOnce();
    expect(adapter.mock.calls[0][0]).toMatchObject({
      method: "delete",
      url: "/admin/cases/17/photo"
    });
  });

  it("상태 변경과 종료 요청을 각각의 엔드포인트로 전송한다", async () => {
    const adapter = vi.fn(async (config) => response(config, {
      timestamp: "2026-07-30T00:00:00Z",
      data: { id: 17, status: config.url.endsWith("/close") ? "CLOSED" : "SEARCHING" }
    }));
    apiClient.defaults.adapter = adapter;

    await expect(updateCaseStatus(17, { status: "SEARCHING", reason: "탐색 시작" }))
      .resolves.toMatchObject({ status: "SEARCHING" });
    await expect(closeCase(17, { reason: "발견", force: false }))
      .resolves.toMatchObject({ status: "CLOSED" });

    expect(adapter.mock.calls.map(([config]) => `${config.method} ${config.url}`)).toEqual([
      "patch /admin/cases/17/status",
      "post /admin/cases/17/close"
    ]);
    expect(JSON.parse(adapter.mock.calls[0][0].data)).toEqual({
      status: "SEARCHING",
      reason: "탐색 시작"
    });
    expect(JSON.parse(adapter.mock.calls[1][0].data)).toEqual({
      reason: "발견",
      force: false
    });
  });
});
