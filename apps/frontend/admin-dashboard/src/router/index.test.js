import { beforeEach, describe, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({
  bootstrap: vi.fn(),
  isAuthenticated: false
}));

vi.mock("../stores/auth", () => ({
  useAuthStore: () => auth
}));

import { authGuard, safeAdminRedirect } from "./authGuard";

const route = (overrides = {}) => ({
  fullPath: "/admin/cases?page=2",
  meta: { title: "사건 관리" },
  path: "/admin/cases",
  query: {},
  ...overrides
});

describe("admin auth guard", () => {
  beforeEach(() => {
    auth.bootstrap.mockReset();
    auth.bootstrap.mockResolvedValue(null);
    auth.isAuthenticated = false;
  });

  it("외부·공개 경로를 로그인 후 복귀 경로로 사용하지 않는다", () => {
    expect(safeAdminRedirect("https://example.com")).toBe("/admin/dashboard");
    expect(safeAdminRedirect("//example.com")).toBe("/admin/dashboard");
    expect(safeAdminRedirect("/report/lookup")).toBe("/admin/dashboard");
    expect(safeAdminRedirect("/admin/cases?page=2")).toBe("/admin/cases?page=2");
  });

  it("보호 경로는 세션을 확인하고 비로그인 사용자의 원래 경로를 보존한다", async () => {
    const result = await authGuard(route());

    expect(auth.bootstrap).toHaveBeenCalledOnce();
    expect(result).toEqual({
      path: "/login",
      query: { redirect: "/admin/cases?page=2" }
    });
  });

  it("유효 세션이면 보호 경로 진입을 허용한다", async () => {
    auth.isAuthenticated = true;
    auth.bootstrap.mockResolvedValue({ id: 1 });

    await expect(authGuard(route())).resolves.toBeUndefined();
  });

  it("로그인 페이지에서 기존 세션을 복원하면 안전한 관리자 경로로 보낸다", async () => {
    auth.isAuthenticated = true;
    const result = await authGuard(route({
      fullPath: "/login?redirect=/admin/cameras",
      meta: { public: true, title: "로그인" },
      path: "/login",
      query: { redirect: "/admin/cameras" }
    }));

    expect(result).toBe("/admin/cameras");
  });

  it("공개 신고자·404 경로에서는 세션을 조회하지 않는다", async () => {
    const result = await authGuard(route({
      fullPath: "/report/lookup",
      meta: { public: true, skipAuthBootstrap: true, title: "신고자 사건 조회" },
      path: "/report/lookup"
    }));

    expect(result).toBeUndefined();
    expect(auth.bootstrap).not.toHaveBeenCalled();
  });

  it("보호 경로의 서버 장애는 로그인 화면에서 구분할 수 있게 전달한다", async () => {
    auth.bootstrap.mockRejectedValue({ status: 503 });

    const result = await authGuard(route());

    expect(result).toEqual({
      path: "/login",
      query: {
        redirect: "/admin/cases?page=2",
        reason: "server-unavailable"
      }
    });
  });
});
