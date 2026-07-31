import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getCurrentAdmin: vi.fn(),
  login: vi.fn(),
  logout: vi.fn()
}));

vi.mock("../api/authApi", () => api);

import { useAuthStore } from "./auth";

const admin = { id: 1, loginId: "admin", name: "Administrator", role: "SUPER_ADMIN" };

describe("auth store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it("동시 bootstrap 호출을 하나로 합치고 세션 사용자를 복원한다", async () => {
    let resolveCurrentAdmin;
    api.getCurrentAdmin.mockReturnValue(new Promise((resolve) => {
      resolveCurrentAdmin = resolve;
    }));
    const store = useAuthStore();

    const first = store.bootstrap();
    const second = store.bootstrap();
    resolveCurrentAdmin(admin);
    await Promise.all([first, second]);

    expect(api.getCurrentAdmin).toHaveBeenCalledOnce();
    expect(store.user).toEqual(admin);
    expect(store.initialized).toBe(true);
    expect(store.isAuthenticated).toBe(true);
    expect(store.isSuperAdmin).toBe(true);
  });

  it("SUPER_ADMIN 역할만 최고 관리자 권한으로 판정한다", () => {
    const store = useAuthStore();

    store.user = { ...admin, role: "ADMIN" };
    expect(store.isSuperAdmin).toBe(false);

    store.user = admin;
    expect(store.isSuperAdmin).toBe(true);
  });

  it("bootstrap의 401만 정상적인 비로그인 상태로 처리한다", async () => {
    api.getCurrentAdmin.mockRejectedValue({ status: 401 });
    const store = useAuthStore();

    await expect(store.bootstrap()).resolves.toBeNull();
    expect(store.user).toBeNull();
    expect(store.initialized).toBe(true);
  });

  it("bootstrap의 네트워크·서버 오류를 삼키지 않는다", async () => {
    const failure = { status: 503, message: "서버 오류" };
    api.getCurrentAdmin.mockRejectedValue(failure);
    const store = useAuthStore();

    await expect(store.bootstrap()).rejects.toBe(failure);
    expect(store.user).toBeNull();
    expect(store.initialized).toBe(false);
  });

  it("로그인 사용자를 메모리에만 저장한다", async () => {
    api.login.mockResolvedValue(admin);
    const storageSpy = vi.spyOn(Storage.prototype, "setItem");
    const store = useAuthStore();

    await store.login({ loginId: "admin", password: "password" });

    expect(api.login).toHaveBeenCalledWith({ loginId: "admin", password: "password" });
    expect(store.user).toEqual(admin);
    expect(store.initialized).toBe(true);
    expect(storageSpy).not.toHaveBeenCalled();
  });

  it("로그인 실패를 그대로 전달하고 인증 상태를 만들지 않는다", async () => {
    const failure = { status: 401, code: "INVALID_CREDENTIALS", message: "로그인 정보가 올바르지 않습니다." };
    api.login.mockRejectedValue(failure);
    const store = useAuthStore();

    await expect(store.login({ loginId: "admin", password: "wrong" })).rejects.toBe(failure);
    expect(store.user).toBeNull();
    expect(store.initialized).toBe(false);
    expect(store.isAuthenticated).toBe(false);
  });

  it("로그아웃 성공과 이미 만료된 401에서는 로컬 세션을 제거한다", async () => {
    const store = useAuthStore();
    store.user = admin;
    store.initialized = true;
    api.logout.mockResolvedValueOnce();

    await store.logout();
    expect(store.user).toBeNull();

    store.user = admin;
    api.logout.mockRejectedValueOnce({ status: 401 });
    await expect(store.logout()).resolves.toBeUndefined();
    expect(store.user).toBeNull();
  });

  it("로그아웃 서버 오류에서는 현재 사용자 상태를 유지한다", async () => {
    const failure = { status: 503, message: "서버 오류" };
    api.logout.mockRejectedValue(failure);
    const store = useAuthStore();
    store.user = admin;
    store.initialized = true;

    await expect(store.logout()).rejects.toBe(failure);
    expect(store.user).toEqual(admin);
    expect(store.isAuthenticated).toBe(true);
  });
});
