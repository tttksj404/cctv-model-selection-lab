import { createApp, nextTick } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { loginMock, routeState, routerReplaceMock } = vi.hoisted(() => ({
  loginMock: vi.fn(),
  routeState: { query: {} },
  routerReplaceMock: vi.fn()
}));

vi.mock("vue-router", () => ({
  useRoute: () => routeState,
  useRouter: () => ({ replace: routerReplaceMock })
}));

vi.mock("../stores/auth", () => ({
  useAuthStore: () => ({ login: loginMock })
}));

import LoginView from "./LoginView.vue";

const settle = async () => {
  for (let index = 0; index < 5; index += 1) {
    await Promise.resolve();
    await nextTick();
  }
};

const inputValue = async (input, value) => {
  input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  await nextTick();
};

describe("LoginView", () => {
  let app;
  let root;

  const mount = () => {
    root = document.createElement("div");
    document.body.appendChild(root);
    app = createApp(LoginView);
    app.mount(root);
  };

  beforeEach(() => {
    routeState.query = {};
    loginMock.mockReset();
    routerReplaceMock.mockReset();
    loginMock.mockResolvedValue({ id: 7, loginId: "control.admin" });
  });

  afterEach(() => {
    app?.unmount();
    root?.remove();
  });

  it("비밀번호 변경 후 새 비밀번호 로그인 안내를 표시하고 원래 프로필로 이동한다", async () => {
    routeState.query = {
      reason: "password-changed",
      redirect: "/admin/profile"
    };
    mount();

    const notice = root.querySelector('[role="status"]');
    expect(notice?.textContent).toContain("비밀번호가 변경되었습니다.");
    expect(notice?.textContent).toContain("새 비밀번호로 다시 로그인해 주세요.");
    expect(root.querySelector(".form-error")).toBeNull();

    const inputs = root.querySelectorAll(".login-card input");
    await inputValue(inputs[0], "control.admin");
    await inputValue(inputs[1], "new-password-123");
    root.querySelector(".login-card").dispatchEvent(
      new Event("submit", { bubbles: true, cancelable: true })
    );
    await settle();

    expect(loginMock).toHaveBeenCalledWith({
      loginId: "control.admin",
      password: "new-password-123"
    });
    expect(routerReplaceMock).toHaveBeenCalledWith("/admin/profile");
  });
});
