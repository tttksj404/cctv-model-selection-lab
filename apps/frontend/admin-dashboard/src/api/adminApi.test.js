import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createAdmin, listAdmins, updateAdminStatus } from "./adminApi";
import { apiClient, setUnauthorizedHandler } from "./httpClient";

const originalAdapter = apiClient.defaults.adapter;
const response = (config, data, status = 200) => ({
  config,
  data,
  headers: {},
  request: {},
  status,
  statusText: status === 201 ? "Created" : "OK"
});

describe("adminApi", () => {
  beforeEach(() => {
    document.cookie = "XSRF-TOKEN=admin-api-token; path=/";
    setUnauthorizedHandler(null);
  });

  afterEach(() => {
    apiClient.defaults.adapter = originalAdapter;
    document.cookie = "XSRF-TOKEN=; Max-Age=0; path=/";
    setUnauthorizedHandler(null);
  });

  it("관리자 목록 응답을 펼쳐 반환한다", async () => {
    const admins = [{ id: 1, loginId: "admin", name: "최고 관리자", role: "SUPER_ADMIN", enabled: true }];
    const adapter = vi.fn(async (config) => response(config, { data: admins }));
    apiClient.defaults.adapter = adapter;

    await expect(listAdmins()).resolves.toEqual(admins);
    expect(adapter.mock.calls[0][0]).toMatchObject({ method: "get", url: "/admins" });
  });

  it("생성 요청에는 역할 없이 계정 필드만 전송한다", async () => {
    const created = { id: 2, loginId: "operator01", name: "운영자", role: "ADMIN", enabled: true };
    const adapter = vi.fn(async (config) => response(config, { data: created }, 201));
    apiClient.defaults.adapter = adapter;

    await expect(createAdmin({
      loginId: "operator01",
      name: "운영자",
      password: "long-password-123"
    })).resolves.toEqual(created);

    expect(adapter.mock.calls[0][0]).toMatchObject({ method: "post", url: "/admins" });
    expect(JSON.parse(adapter.mock.calls[0][0].data)).toEqual({
      loginId: "operator01",
      name: "운영자",
      password: "long-password-123"
    });
  });

  it("식별자를 인코딩하고 상태만 PATCH한다", async () => {
    const adapter = vi.fn(async (config) => response(config, {
      data: { id: "admin/2", enabled: false }
    }));
    apiClient.defaults.adapter = adapter;

    await updateAdminStatus("admin/2", false);

    expect(adapter.mock.calls[0][0]).toMatchObject({
      method: "patch",
      url: "/admins/admin%2F2/status"
    });
    expect(JSON.parse(adapter.mock.calls[0][0].data)).toEqual({ enabled: false });
  });
});
