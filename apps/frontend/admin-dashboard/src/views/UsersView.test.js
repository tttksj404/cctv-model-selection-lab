import { createPinia, setActivePinia } from "pinia";
import { createApp, nextTick } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { createAdminMock, listAdminsMock, updateAdminStatusMock } = vi.hoisted(() => ({
  createAdminMock: vi.fn(),
  listAdminsMock: vi.fn(),
  updateAdminStatusMock: vi.fn()
}));

vi.mock("../api/adminApi", () => ({
  createAdmin: createAdminMock,
  listAdmins: listAdminsMock,
  updateAdminStatus: updateAdminStatusMock
}));

import { useAuthStore } from "../stores/auth";
import UsersView from "./UsersView.vue";

const admin = (id, overrides = {}) => ({
  id,
  loginId: `operator${String(id).padStart(2, "0")}`,
  name: `관리자 ${id}`,
  role: "ADMIN",
  enabled: true,
  createdAt: `2026-07-${String(Math.min(id, 28)).padStart(2, "0")}T01:00:00Z`,
  ...overrides
});

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

const findButton = (root, text) => [...root.querySelectorAll("button")]
  .find((button) => button.textContent.trim().includes(text));

const inputValue = async (input, value) => {
  input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  await nextTick();
};

describe("UsersView", () => {
  let app;
  let root;

  const mount = (currentUser = admin(1, { role: "SUPER_ADMIN" })) => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const auth = useAuthStore();
    auth.user = currentUser;
    auth.initialized = true;

    root = document.createElement("div");
    document.body.appendChild(root);
    app = createApp(UsersView);
    app.use(pinia);
    app.mount(root);
  };

  beforeEach(() => {
    listAdminsMock.mockReset();
    createAdminMock.mockReset();
    updateAdminStatusMock.mockReset();
    listAdminsMock.mockResolvedValue([]);
  });

  afterEach(() => {
    app?.unmount();
    root?.remove();
  });

  it("실제 관리자 목록을 표시하고 클라이언트 페이지네이션을 적용한다", async () => {
    const admins = Array.from({ length: 11 }, (_, index) => admin(index + 1, index === 0
      ? { role: "SUPER_ADMIN", name: "최고 관리자" }
      : {}));
    listAdminsMock.mockResolvedValue(admins);

    mount(admins[0]);
    await settle();

    expect(listAdminsMock).toHaveBeenCalledOnce();
    expect(root.textContent).toContain("최고 관리자");
    expect(root.textContent).toContain("전체 11건");
    expect(root.textContent).not.toContain("operator11");

    findButton(root, "다음").click();
    await settle();
    expect(root.textContent).toContain("operator11");
  });

  it("목록 오류를 표시하고 다시 시도한다", async () => {
    listAdminsMock
      .mockRejectedValueOnce(new Error("관리자 조회 오류"))
      .mockResolvedValueOnce([admin(1, { role: "SUPER_ADMIN" })]);

    mount();
    await settle();
    expect(root.textContent).toContain("관리자 조회 오류");

    findButton(root, "다시 시도").click();
    await settle();
    expect(listAdminsMock).toHaveBeenCalledTimes(2);
    expect(root.textContent).toContain("operator01");
  });

  it("배열이 아닌 목록 응답을 빈 목록으로 숨기지 않고 계약 오류로 표시한다", async () => {
    listAdminsMock.mockResolvedValue({ admins: [] });

    mount();
    await settle();

    expect(root.textContent).toContain("관리자 계정 목록 응답 형식이 올바르지 않습니다.");
    expect(root.textContent).not.toContain("조회된 데이터가 없습니다.");
  });

  it("초기 목록을 불러오는 동안 계정 생성을 막아 오래된 응답의 덮어쓰기를 방지한다", async () => {
    const request = deferred();
    listAdminsMock.mockReturnValue(request.promise);

    mount();
    await nextTick();

    expect(findButton(root, "관리자 계정 생성").disabled).toBe(true);

    request.resolve([admin(1, { role: "SUPER_ADMIN" })]);
    await settle();
    expect(findButton(root, "관리자 계정 생성").disabled).toBe(false);
  });

  it("생성 값을 정규화하고 처리 중 중복 제출을 막는다", async () => {
    listAdminsMock.mockResolvedValue([admin(1, { role: "SUPER_ADMIN" })]);
    const request = deferred();
    createAdminMock.mockReturnValue(request.promise);
    mount();
    await settle();

    findButton(root, "관리자 계정 생성").click();
    await nextTick();
    const inputs = root.querySelectorAll(".admin-create-form input");
    await inputValue(inputs[0], "  Operator.New  ");
    await inputValue(inputs[1], "  신규 관리자  ");
    await inputValue(inputs[2], "long-password-123");
    await inputValue(inputs[3], "long-password-123");

    const form = root.querySelector(".admin-create-form");
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await settle();

    expect(createAdminMock).toHaveBeenCalledOnce();
    expect(createAdminMock).toHaveBeenCalledWith({
      loginId: "operator.new",
      name: "신규 관리자",
      password: "long-password-123"
    });
    expect(findButton(root, "생성 중").disabled).toBe(true);

    request.resolve(admin(2, { loginId: "operator.new", name: "신규 관리자" }));
    await settle();
    expect(root.querySelector(".admin-create-modal")).toBeNull();
    expect(root.textContent).toContain("operator.new");
  });

  it("잘못된 생성 값은 API를 호출하지 않고 필드 오류를 표시한다", async () => {
    listAdminsMock.mockResolvedValue([admin(1, { role: "SUPER_ADMIN" })]);
    mount();
    await settle();

    findButton(root, "관리자 계정 생성").click();
    await nextTick();
    const inputs = root.querySelectorAll(".admin-create-form input");
    await inputValue(inputs[0], "A");
    await inputValue(inputs[1], "");
    await inputValue(inputs[2], "short");
    await inputValue(inputs[3], "different");
    root.querySelector(".admin-create-form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await settle();

    expect(createAdminMock).not.toHaveBeenCalled();
    expect(root.textContent).toContain("4~50자");
    expect(root.textContent).toContain("이름을 입력해 주세요.");
    expect(root.textContent).toContain("비밀번호가 일치하지 않습니다.");
  });

  it("중복 로그인 아이디 오류는 아이디를 다시 입력하면 지운다", async () => {
    listAdminsMock.mockResolvedValue([admin(1, { role: "SUPER_ADMIN" })]);
    createAdminMock.mockRejectedValue({
      code: "ADMIN_LOGIN_ID_CONFLICT",
      status: 409,
      message: "이미 사용 중인 관리자 로그인 ID입니다."
    });
    mount();
    await settle();

    findButton(root, "관리자 계정 생성").click();
    await nextTick();
    const inputs = root.querySelectorAll(".admin-create-form input");
    await inputValue(inputs[0], "duplicate");
    await inputValue(inputs[1], "중복 관리자");
    await inputValue(inputs[2], "long-password-123");
    await inputValue(inputs[3], "long-password-123");
    root.querySelector(".admin-create-form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await settle();

    expect(root.textContent).toContain("이미 사용 중인 로그인 아이디입니다.");

    await inputValue(inputs[0], "available");
    expect(root.textContent).not.toContain("이미 사용 중인 로그인 아이디입니다.");
  });

  it("현재 계정 변경을 막고 다른 계정은 확인 후 비활성화한다", async () => {
    const current = admin(1, { role: "SUPER_ADMIN", name: "현재 관리자" });
    const target = admin(2, { name: "대상 관리자" });
    listAdminsMock.mockResolvedValue([current, target]);
    updateAdminStatusMock.mockResolvedValue({ ...target, enabled: false });
    mount(current);
    await settle();

    const rows = [...root.querySelectorAll("tbody tr")];
    expect(rows[0].querySelector("button").disabled).toBe(true);
    rows[1].querySelector("button").click();
    await nextTick();
    expect(root.textContent).toContain("기존 세션이 종료");

    root.querySelector(".modal .primary-button").click();
    await settle();
    expect(updateAdminStatusMock).toHaveBeenCalledWith(2, false);
    expect(rows[1].textContent).toContain("비활성");
  });

  it("상태 변경 충돌은 확인 모달을 유지한 채 메시지를 표시한다", async () => {
    const current = admin(1, { role: "SUPER_ADMIN" });
    const target = admin(2);
    listAdminsMock.mockResolvedValue([current, target]);
    updateAdminStatusMock.mockRejectedValue({ status: 409, message: "마지막 최고 관리자는 비활성화할 수 없습니다." });
    mount(current);
    await settle();

    root.querySelectorAll("tbody tr")[1].querySelector("button").click();
    await nextTick();
    root.querySelector(".modal .primary-button").click();
    await settle();

    expect(root.querySelector(".modal")).not.toBeNull();
    expect(root.textContent).toContain("마지막 최고 관리자는 비활성화할 수 없습니다.");
  });
});
