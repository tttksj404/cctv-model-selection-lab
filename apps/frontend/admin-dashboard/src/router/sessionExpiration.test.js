import { describe, expect, it, vi } from "vitest";
import { createSessionExpirationHandler } from "./sessionExpiration";

const createContext = ({ authenticated = true, path = "/admin/cases", fullPath = "/admin/cases?page=2" } = {}) => {
  const auth = {
    isAuthenticated: authenticated,
    expireSession: vi.fn()
  };
  const router = {
    currentRoute: { value: { path, fullPath } },
    replace: vi.fn().mockResolvedValue(undefined)
  };

  return { auth, router, handler: createSessionExpirationHandler({ auth, router }) };
};

describe("session expiration handler", () => {
  it("비로그인 상태의 401은 로그인 이동으로 처리하지 않는다", () => {
    const { auth, router, handler } = createContext({ authenticated: false });

    handler({ status: 401, code: "INVALID_CREDENTIALS" });

    expect(auth.expireSession).not.toHaveBeenCalled();
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("로그인 상태의 세션 만료는 상태를 지우고 원래 관리자 경로를 보존한다", async () => {
    const { auth, router, handler } = createContext();

    await handler({ status: 401, code: "SESSION_EXPIRED" });

    expect(auth.expireSession).toHaveBeenCalledOnce();
    expect(router.replace).toHaveBeenCalledWith({
      path: "/login",
      query: {
        redirect: "/admin/cases?page=2",
        reason: "session-expired"
      }
    });
  });

  it("401이 아닌 오류는 로그인 상태를 유지한다", () => {
    const { auth, router, handler } = createContext();

    handler({ status: 503, code: "SERVICE_UNAVAILABLE" });

    expect(auth.expireSession).not.toHaveBeenCalled();
    expect(router.replace).not.toHaveBeenCalled();
  });
});
