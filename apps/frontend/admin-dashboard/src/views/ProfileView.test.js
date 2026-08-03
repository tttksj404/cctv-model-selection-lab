import { createPinia, setActivePinia } from "pinia";
import { createApp, nextTick } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const {
  getCurrentAdminMock,
  loginMock,
  logoutMock,
  routerReplaceMock,
  updateCurrentAdminMock
} = vi.hoisted(() => ({
  getCurrentAdminMock: vi.fn(),
  loginMock: vi.fn(),
  logoutMock: vi.fn(),
  routerReplaceMock: vi.fn(),
  updateCurrentAdminMock: vi.fn()
}));

vi.mock("vue-router", () => ({
  useRouter: () => ({ replace: routerReplaceMock })
}));

vi.mock("../api/authApi", () => ({
  getCurrentAdmin: getCurrentAdminMock,
  login: loginMock,
  logout: logoutMock,
  updateCurrentAdmin: updateCurrentAdminMock
}));

import { useAuthStore } from "../stores/auth";
import ProfileView from "./ProfileView.vue";

const currentAdmin = {
  id: 7,
  loginId: "control.admin",
  name: "관제 관리자",
  role: "ADMIN"
};

const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
};

const settle = async () => {
  for (let index = 0; index < 6; index += 1) {
    await Promise.resolve();
    await nextTick();
  }
};

const inputValue = async (input, value) => {
  input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  await nextTick();
};

const submit = async (form) => {
  form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  await settle();
};

const findButton = (root, text) => [...root.querySelectorAll("button")]
  .find((button) => button.textContent.trim().includes(text));

describe("ProfileView", () => {
  let app;
  let root;
  let auth;

  const mount = () => {
    const pinia = createPinia();
    setActivePinia(pinia);
    auth = useAuthStore();
    auth.user = { ...currentAdmin };
    auth.initialized = true;

    root = document.createElement("div");
    document.body.appendChild(root);
    app = createApp(ProfileView);
    app.use(pinia);
    app.mount(root);
  };

  beforeEach(() => {
    getCurrentAdminMock.mockReset();
    updateCurrentAdminMock.mockReset();
    loginMock.mockReset();
    logoutMock.mockReset();
    routerReplaceMock.mockReset();
    getCurrentAdminMock.mockResolvedValue({ ...currentAdmin });
    updateCurrentAdminMock.mockResolvedValue({
      admin: { ...currentAdmin },
      reauthenticationRequired: false
    });
  });

  afterEach(() => {
    app?.unmount();
    root?.remove();
  });

  it("진입 즉시 현재 관리자를 다시 조회하고 확인 모달 없이 읽기 전용 계정 정보를 표시한다", async () => {
    const request = deferred();
    getCurrentAdminMock.mockReturnValue(request.promise);

    mount();

    expect(getCurrentAdminMock).toHaveBeenCalledOnce();
    expect(root.textContent).toContain("프로필 정보를 불러오는 중입니다.");
    expect(root.querySelector(".modal-backdrop")).toBeNull();

    request.resolve({ ...currentAdmin });
    await settle();

    const readonlyInputs = [...root.querySelectorAll(".profile-readonly-grid input")];
    expect(readonlyInputs.map((input) => input.value)).toEqual(["7", "control.admin", "ADMIN"]);
    expect(readonlyInputs.every((input) => input.readOnly)).toBe(true);
    expect(root.textContent).not.toContain("관리자 확인");
    expect(root.textContent).not.toContain("관리자 번호");
    expect(root.textContent).not.toContain("이메일");
    expect(root.textContent).not.toContain("연락처");
  });

  it("프로필 조회 오류를 표시하고 다시 시도한다", async () => {
    getCurrentAdminMock
      .mockRejectedValueOnce(new Error("프로필 조회 오류"))
      .mockResolvedValueOnce({ ...currentAdmin });

    mount();
    await settle();
    expect(root.textContent).toContain("프로필 조회 오류");

    findButton(root, "다시 시도").click();
    await settle();

    expect(getCurrentAdminMock).toHaveBeenCalledTimes(2);
    expect(root.querySelector('input[name="loginId"]').value).toBe("control.admin");
  });

  it("이름을 trim해 별도 PATCH payload로 보내고 공백·길이·무변경 입력은 차단한다", async () => {
    mount();
    await settle();
    const nameInput = root.querySelector('input[name="name"]');
    const nameForm = root.querySelector(".profile-name-form");

    await submit(nameForm);
    expect(root.textContent).toContain("변경된 이름이 없습니다.");
    expect(updateCurrentAdminMock).not.toHaveBeenCalled();

    await inputValue(nameInput, "   ");
    await submit(nameForm);
    expect(root.textContent).toContain("이름을 입력해 주세요.");

    await inputValue(nameInput, "가".repeat(51));
    await submit(nameForm);
    expect(root.textContent).toContain("이름은 50자 이하로 입력해 주세요.");
    expect(updateCurrentAdminMock).not.toHaveBeenCalled();

    updateCurrentAdminMock.mockResolvedValueOnce({
      admin: { ...currentAdmin, name: "변경 관리자" },
      reauthenticationRequired: false
    });
    await inputValue(nameInput, "  변경 관리자  ");
    await submit(nameForm);

    expect(updateCurrentAdminMock).toHaveBeenCalledOnce();
    expect(updateCurrentAdminMock).toHaveBeenCalledWith({ name: "변경 관리자" });
    expect(nameInput.value).toBe("변경 관리자");
    expect(root.textContent).toContain("이름이 변경되었습니다.");
  });

  it("새 비밀번호 길이·UTF-8 바이트·확인 일치를 검증한다", async () => {
    mount();
    await settle();
    const passwordForm = root.querySelector(".profile-password-form");
    const currentPassword = root.querySelector('input[name="currentPassword"]');
    const newPassword = root.querySelector('input[name="newPassword"]');
    const passwordConfirm = root.querySelector('input[name="passwordConfirm"]');

    await inputValue(newPassword, "short");
    await inputValue(passwordConfirm, "different");
    await submit(passwordForm);
    expect(root.textContent).toContain("현재 비밀번호를 입력해 주세요.");
    expect(root.textContent).toContain("12~64자");
    expect(root.textContent).toContain("새 비밀번호가 일치하지 않습니다.");

    await inputValue(currentPassword, "current-password");
    await inputValue(newPassword, "가".repeat(25));
    await inputValue(passwordConfirm, "가".repeat(25));
    await submit(passwordForm);
    expect(root.textContent).toContain("UTF-8 기준 72바이트");
    expect(updateCurrentAdminMock).not.toHaveBeenCalled();
  });

  it("현재 비밀번호 불일치 API 오류를 현재 비밀번호 필드에 표시한다", async () => {
    updateCurrentAdminMock.mockRejectedValueOnce({
      code: "CURRENT_PASSWORD_MISMATCH",
      message: "현재 비밀번호가 올바르지 않습니다."
    });
    mount();
    await settle();

    const currentPassword = root.querySelector('input[name="currentPassword"]');
    await inputValue(currentPassword, "wrong-current-password");
    await inputValue(root.querySelector('input[name="newPassword"]'), "new-password-123");
    await inputValue(root.querySelector('input[name="passwordConfirm"]'), "new-password-123");
    await submit(root.querySelector(".profile-password-form"));

    expect(updateCurrentAdminMock).toHaveBeenCalledWith({
      currentPassword: "wrong-current-password",
      newPassword: "new-password-123"
    });
    expect(currentPassword.getAttribute("aria-invalid")).toBe("true");
    expect(root.textContent).toContain("현재 비밀번호가 올바르지 않습니다.");

    await inputValue(currentPassword, "correct-current-password");
    expect(root.textContent).not.toContain("현재 비밀번호가 올바르지 않습니다.");
  });

  it("비밀번호 변경 후 logout API 없이 세션을 만료하고 로그인 완료 안내 경로로 이동한다", async () => {
    updateCurrentAdminMock.mockResolvedValueOnce({
      admin: { ...currentAdmin },
      reauthenticationRequired: true
    });
    mount();
    await settle();

    await inputValue(root.querySelector('input[name="currentPassword"]'), "current-password");
    await inputValue(root.querySelector('input[name="newPassword"]'), "new-password-123");
    await inputValue(root.querySelector('input[name="passwordConfirm"]'), "new-password-123");
    await submit(root.querySelector(".profile-password-form"));

    expect(auth.user).toBeNull();
    expect(logoutMock).not.toHaveBeenCalled();
    expect(routerReplaceMock).toHaveBeenCalledWith(
      "/login?reason=password-changed&redirect=/admin/profile"
    );
  });
});
