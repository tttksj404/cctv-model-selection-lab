import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  ApiClientError,
  apiClient,
  issueCsrfToken,
  setUnauthorizedHandler,
  unwrapData,
  unwrapPagedData
} from "./httpClient";

const originalAdapter = apiClient.defaults.adapter;

const response = (config, data, status = 200) => ({
  config,
  data,
  headers: {},
  request: {},
  status,
  statusText: status === 204 ? "No Content" : "OK"
});

const clearCsrfCookie = () => {
  document.cookie = "XSRF-TOKEN=; Max-Age=0; path=/";
};

describe("httpClient", () => {
  beforeEach(() => {
    clearCsrfCookie();
    setUnauthorizedHandler(null);
  });

  afterEach(() => {
    apiClient.defaults.adapter = originalAdapter;
    clearCsrfCookie();
    setUnauthorizedHandler(null);
  });

  it("일반·페이지·204 응답을 공통 형식으로 푼다", () => {
    expect(unwrapData({ timestamp: "now", data: { id: 1 } })).toEqual({ id: 1 });
    expect(unwrapPagedData({ data: [1, 2], meta: { page: 0 } })).toEqual({
      data: [1, 2],
      meta: { page: 0 }
    });
    expect(unwrapData(response({}, "", 204))).toBeUndefined();
  });

  it("잘못된 성공 응답은 ApiClientError로 거부한다", () => {
    expect(() => unwrapData({ timestamp: "now" })).toThrowError(ApiClientError);
    expect(() => unwrapPagedData({ data: [] })).toThrowError(ApiClientError);
  });

  it("동시에 시작된 변경 요청은 CSRF 발급 요청 하나를 공유한다", async () => {
    const adapter = vi.fn(async (config) => {
      if (config.url === "/auth/csrf") {
        document.cookie = "XSRF-TOKEN=csrf-token; path=/";
        return response(config, "", 204);
      }
      return response(config, { timestamp: "now", data: { ok: true } });
    });
    apiClient.defaults.adapter = adapter;

    await Promise.all([
      apiClient.post("/resource-a", { value: 1 }),
      apiClient.patch("/resource-b", { value: 2 })
    ]);

    expect(adapter.mock.calls.filter(([config]) => config.url === "/auth/csrf")).toHaveLength(1);
    expect(apiClient.defaults.withCredentials).toBe(true);
    expect(apiClient.defaults.withXSRFToken).toBe(true);
    expect(apiClient.defaults.xsrfCookieName).toBe("XSRF-TOKEN");
    expect(apiClient.defaults.xsrfHeaderName).toBe("X-XSRF-TOKEN");
  });

  it("CSRF 응답 뒤 쿠키가 없으면 변경 요청을 보내지 않는다", async () => {
    const adapter = vi.fn(async (config) => response(config, "", 204));
    apiClient.defaults.adapter = adapter;

    await expect(apiClient.post("/resource", { value: 1 })).rejects.toMatchObject({
      status: null,
      code: "CSRF_TOKEN_MISSING",
      message: "보안 토큰을 발급받지 못했습니다."
    });
    expect(adapter).toHaveBeenCalledOnce();
    expect(adapter.mock.calls[0][0].url).toBe("/auth/csrf");
  });

  it("강제 CSRF 갱신은 기존 쿠키가 있어도 다시 발급한다", async () => {
    document.cookie = "XSRF-TOKEN=old-token; path=/";
    const adapter = vi.fn(async (config) => response(config, "", 204));
    apiClient.defaults.adapter = adapter;

    await issueCsrfToken({ force: true });

    expect(adapter).toHaveBeenCalledOnce();
    expect(adapter.mock.calls[0][0].url).toBe("/auth/csrf");
  });

  it("백엔드 오류를 정규화하고 등록된 401 처리기에 전달한다", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    apiClient.defaults.adapter = vi.fn(async (config) => Promise.reject({
      config,
      response: {
        status: 401,
        data: {
          timestamp: "2026-07-30T00:00:00Z",
          status: 401,
          code: "SESSION_EXPIRED",
          message: "다른 로그인으로 현재 세션이 종료되었습니다."
        }
      }
    }));

    const error = await apiClient.get("/admins/me").catch((caught) => caught);

    expect(error).toMatchObject({
      name: "ApiClientError",
      status: 401,
      code: "SESSION_EXPIRED",
      message: "다른 로그인으로 현재 세션이 종료되었습니다."
    });
    expect(handler).toHaveBeenCalledOnce();
    expect(handler).toHaveBeenCalledWith(error);
  });

  it("응답이 없는 오류는 네트워크 오류로 정규화한다", async () => {
    apiClient.defaults.adapter = vi.fn(async (config) => Promise.reject({ config }));

    await expect(apiClient.get("/admins/me")).rejects.toMatchObject({
      status: null,
      code: "NETWORK_ERROR",
      message: "서버에 연결할 수 없습니다."
    });
  });
});
