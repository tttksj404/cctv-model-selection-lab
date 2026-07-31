import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getCurrentAdmin, login, logout } from "./authApi";
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

const setCsrfCookie = (value) => {
  document.cookie = `XSRF-TOKEN=${value}; path=/`;
};

const clearCsrfCookie = () => {
  document.cookie = "XSRF-TOKEN=; Max-Age=0; path=/";
};

describe("authApi", () => {
  beforeEach(() => {
    clearCsrfCookie();
    setUnauthorizedHandler(null);
  });

  afterEach(() => {
    apiClient.defaults.adapter = originalAdapter;
    clearCsrfCookie();
    setUnauthorizedHandler(null);
  });

  it("CSRF 발급, 세션 로그인, CSRF 재발급 순서로 로그인한다", async () => {
    let csrfSequence = 0;
    const adapter = vi.fn(async (config) => {
      if (config.url === "/auth/csrf") {
        csrfSequence += 1;
        setCsrfCookie(`token-${csrfSequence}`);
        return response(config, "", 204);
      }
      if (config.url === "/auth/admin/login") {
        clearCsrfCookie();
        return response(config, {
          timestamp: "2026-07-30T00:00:00Z",
          data: { id: 1, loginId: "admin", name: "Administrator", role: "SUPER_ADMIN" }
        });
      }
      throw new Error(`Unexpected request: ${config.url}`);
    });
    apiClient.defaults.adapter = adapter;

    const admin = await login({ loginId: "admin", password: "password" });

    expect(admin).toEqual({ id: 1, loginId: "admin", name: "Administrator", role: "SUPER_ADMIN" });
    expect(adapter.mock.calls.map(([config]) => `${config.method} ${config.url}`)).toEqual([
      "get /auth/csrf",
      "post /auth/admin/login",
      "get /auth/csrf"
    ]);
    expect(JSON.parse(adapter.mock.calls[1][0].data)).toEqual({
      loginId: "admin",
      password: "password"
    });
  });

  it("로그인 성공 뒤 CSRF 재발급 실패는 성공한 세션 응답을 뒤집지 않는다", async () => {
    setCsrfCookie("existing-token");
    const adapter = vi.fn(async (config) => {
      if (config.url === "/auth/admin/login") {
        return response(config, {
          timestamp: "2026-07-30T00:00:00Z",
          data: { id: 1, loginId: "admin", name: "Administrator", role: "SUPER_ADMIN" }
        });
      }
      return Promise.reject({ config });
    });
    apiClient.defaults.adapter = adapter;

    await expect(login({ loginId: "admin", password: "password" })).resolves.toMatchObject({ id: 1 });
  });

  it("서버 로그아웃 뒤 CSRF를 재발급한다", async () => {
    setCsrfCookie("authenticated-token");
    const adapter = vi.fn(async (config) => {
      if (config.url === "/auth/admin/logout") {
        clearCsrfCookie();
        return response(config, "", 204);
      }
      if (config.url === "/auth/csrf") {
        setCsrfCookie("anonymous-token");
        return response(config, "", 204);
      }
      throw new Error(`Unexpected request: ${config.url}`);
    });
    apiClient.defaults.adapter = adapter;

    await logout();

    expect(adapter.mock.calls.map(([config]) => `${config.method} ${config.url}`)).toEqual([
      "post /auth/admin/logout",
      "get /auth/csrf"
    ]);
  });

  it("현재 관리자 응답의 역할을 그대로 반환한다", async () => {
    const current = { id: 1, loginId: "admin", name: "Administrator", role: "SUPER_ADMIN" };
    const adapter = vi.fn(async (config) => response(config, { data: current }));
    apiClient.defaults.adapter = adapter;

    await expect(getCurrentAdmin()).resolves.toEqual(current);
    expect(adapter.mock.calls[0][0]).toMatchObject({ method: "get", url: "/admins/me" });
  });
});
