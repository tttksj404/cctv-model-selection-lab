import { createApp, nextTick, reactive } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const caseApi = vi.hoisted(() => ({
  createCase: vi.fn(),
  deleteCasePhoto: vi.fn(),
  getCase: vi.fn(),
  putCasePhoto: vi.fn(),
  updateCase: vi.fn()
}));

const routing = vi.hoisted(() => ({
  route: { params: {}, query: {} },
  router: {
    back: vi.fn(),
    push: vi.fn(() => Promise.resolve()),
    replace: vi.fn(() => Promise.resolve())
  }
}));

vi.mock("../api/caseApi", () => caseApi);
vi.mock("vue-router", () => ({
  useRoute: () => routing.route,
  useRouter: () => routing.router
}));

import CaseFormView from "./CaseFormView.vue";

const rawCase = (overrides = {}) => ({
  id: 17,
  caseNumber: "EFU-0123456789ABCDEFGHJKMNPQRS",
  status: "RECEIVED",
  reporter: { id: 9, name: "박신고", phone: "01012345678", relation: "보호자" },
  reportContent: "귀가하지 않아 신고했습니다.",
  missingName: "김민수",
  gender: "MALE",
  birthYear: 1952,
  appearance: { hair: "짧은 머리", upperClothing: "검은 외투" },
  photoUrl: "https://storage.example/photo.jpg",
  lastSeenTime: "2026-07-20T00:10:00Z",
  lastSeenLat: 37.5,
  lastSeenLng: 127.03,
  lastSeenAddress: "서울 강남구",
  reportedAt: "2026-07-20T01:30:00Z",
  closedAt: null,
  updatedAt: "2026-07-20T02:00:00Z",
  ...overrides
});

const mountedApps = [];
const originalCreateObjectUrl = Object.getOwnPropertyDescriptor(URL, "createObjectURL");
const originalRevokeObjectUrl = Object.getOwnPropertyDescriptor(URL, "revokeObjectURL");

async function flushUi() {
  for (let index = 0; index < 5; index += 1) await Promise.resolve();
  await nextTick();
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

async function mountView() {
  const root = document.createElement("div");
  document.body.append(root);
  const app = createApp(CaseFormView);
  app.mount(root);
  mountedApps.push({ app, root });
  await flushUi();
  return root;
}

function buttonByText(root, text) {
  return [...root.querySelectorAll("button")]
    .find((button) => button.textContent.trim() === text);
}

function fieldByTitle(root, title, selector = "input, textarea, select") {
  const heading = [...root.querySelectorAll(".field-title")]
    .find((element) => element.textContent.trim() === title);
  return heading?.closest("label")?.querySelector(selector);
}

function setValue(element, value) {
  element.value = value;
  element.dispatchEvent(new Event(element.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
}

function choosePhoto(root, name = "person.png") {
  const input = root.querySelector('input[type="file"]');
  const photo = new File(["image"], name, { type: "image/png" });
  Object.defineProperty(input, "files", { configurable: true, value: [photo] });
  input.dispatchEvent(new Event("change", { bubbles: true }));
  return photo;
}

function fillRequiredForm(root) {
  setValue(fieldByTitle(root, "신고자 이름"), "박신고");
  setValue(fieldByTitle(root, "연락처"), "010-1234-5678");
  setValue(fieldByTitle(root, "이름"), "테스트 실종자");
  setValue(fieldByTitle(root, "년생"), "1950");
  setValue(root.querySelector(".head-field input"), "짧은 검은 머리");
  setValue(fieldByTitle(root, "마지막 목격 날짜"), "2026-07-30");
  setValue(fieldByTitle(root, "마지막 목격 시간"), "14:30");
  setValue(fieldByTitle(root, "마지막 목격 위치"), "서울특별시 강남구");
  setValue(fieldByTitle(root, "실종 경위", "textarea"), "산책 후 귀가하지 않았습니다.");
  return choosePhoto(root);
}

beforeEach(() => {
  vi.clearAllMocks();
  routing.route = reactive({ params: {}, query: {}, path: "/admin/cases/new" });
  localStorage.clear();
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: vi.fn(() => "blob:case-photo")
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: vi.fn()
  });
});

afterEach(() => {
  for (const { app, root } of mountedApps.splice(0)) {
    app.unmount();
    root.remove();
  }
  localStorage.clear();
  if (originalCreateObjectUrl) Object.defineProperty(URL, "createObjectURL", originalCreateObjectUrl);
  else delete URL.createObjectURL;
  if (originalRevokeObjectUrl) Object.defineProperty(URL, "revokeObjectURL", originalRevokeObjectUrl);
  else delete URL.revokeObjectURL;
});

describe("CaseFormView", () => {
  it("필수 입력값과 사진이 없으면 등록 확인을 열지 않는다", async () => {
    const root = await mountView();

    buttonByText(root, "사건 등록 · ID 발급").click();
    await nextTick();

    expect(root.querySelector('[role="dialog"]')).toBeNull();
    expect(root.textContent).toContain("사진을 선택해 주세요.");
    expect(root.textContent).toContain("인상착의 항목을 하나 이상 입력해 주세요.");
    expect(caseApi.createCase).not.toHaveBeenCalled();
  });

  it("기본 사건을 만든 다음 반환된 ID로 사진을 업로드한다", async () => {
    caseApi.createCase.mockResolvedValue({
      id: 31,
      caseNumber: "EFU-NEW-31",
      status: "RECEIVED",
      reportedAt: "2026-07-30T05:30:00Z"
    });
    caseApi.putCasePhoto.mockResolvedValue({ photoUrl: "https://storage.example/31.jpg" });
    const root = await mountView();
    const photo = fillRequiredForm(root);

    buttonByText(root, "사건 등록 · ID 발급").click();
    await nextTick();
    buttonByText(root, "등록").click();
    await flushUi();

    expect(caseApi.createCase).toHaveBeenCalledWith(expect.objectContaining({
      missingName: "테스트 실종자",
      gender: "FEMALE",
      birthYear: 1950,
      lastSeenTime: "2026-07-30T14:30:00+09:00",
      lastSeenAddress: "서울특별시 강남구"
    }));
    expect(caseApi.putCasePhoto).toHaveBeenCalledWith(31, photo);
    expect(caseApi.createCase.mock.invocationCallOrder[0])
      .toBeLessThan(caseApi.putCasePhoto.mock.invocationCallOrder[0]);
    expect(routing.router.push).toHaveBeenCalledWith("/admin/cases/31");
  });

  it("사진 업로드가 실패하면 사건 POST를 반복하지 않고 수정 화면으로 보낸다", async () => {
    caseApi.createCase.mockResolvedValue({ id: 32, caseNumber: "EFU-NEW-32", status: "RECEIVED" });
    caseApi.putCasePhoto.mockRejectedValue({ status: 503, message: "스토리지를 사용할 수 없습니다." });
    caseApi.getCase.mockResolvedValue(rawCase({
      id: 32,
      caseNumber: "EFU-NEW-32",
      photoUrl: null
    }));
    const root = await mountView();
    fillRequiredForm(root);

    buttonByText(root, "사건 등록 · ID 발급").click();
    await nextTick();
    buttonByText(root, "등록").click();
    await flushUi();

    expect(caseApi.createCase).toHaveBeenCalledTimes(1);
    expect(caseApi.putCasePhoto).toHaveBeenCalledTimes(1);
    expect(routing.router.replace).toHaveBeenCalledWith({
      path: "/admin/cases/32/edit",
      query: { photoUpload: "failed" }
    });
    expect(routing.router.push).not.toHaveBeenCalled();

    routing.route.path = "/admin/cases/32/edit";
    routing.route.params.caseId = "32";
    routing.route.query.photoUpload = "failed";
    await flushUi();
    expect(root.textContent).toContain("EFU-NEW-32 · ID 32 사건은 등록됐지만 사진 업로드에 실패했습니다.");

    caseApi.putCasePhoto.mockResolvedValue({ photoUrl: "https://storage.example/32.jpg" });
    const retryPhoto = choosePhoto(root, "retry.png");
    buttonByText(root, "사건 정보 저장").click();
    await nextTick();
    buttonByText(root, "저장").click();
    await flushUi();

    expect(caseApi.createCase).toHaveBeenCalledTimes(1);
    expect(caseApi.updateCase).not.toHaveBeenCalled();
    expect(caseApi.putCasePhoto).toHaveBeenCalledTimes(2);
    expect(caseApi.putCasePhoto).toHaveBeenLastCalledWith("32", retryPhoto);
    expect(routing.router.push).toHaveBeenCalledWith("/admin/cases/32");
  });

  it("수정 화면에서 사진만 선택하면 PATCH를 생략하고 사진만 교체한다", async () => {
    routing.route.path = "/admin/cases/17/edit";
    routing.route.params = { caseId: "17" };
    caseApi.getCase.mockResolvedValue(rawCase());
    caseApi.putCasePhoto.mockResolvedValue({ photoUrl: "https://storage.example/new.jpg" });
    const root = await mountView();
    const photo = choosePhoto(root, "replacement.png");

    buttonByText(root, "사건 정보 저장").click();
    await nextTick();
    buttonByText(root, "저장").click();
    await flushUi();

    expect(caseApi.updateCase).not.toHaveBeenCalled();
    expect(caseApi.putCasePhoto).toHaveBeenCalledWith("17", photo);
    expect(routing.router.push).toHaveBeenCalledWith("/admin/cases/17");
  });

  it("수정된 중첩 필드만 PATCH하고 주소 변경 시 기존 좌표를 제거한다", async () => {
    routing.route.path = "/admin/cases/17/edit";
    routing.route.params = { caseId: "17" };
    caseApi.getCase.mockResolvedValue(rawCase());
    caseApi.updateCase.mockResolvedValue(rawCase({
      reporter: { id: 9, name: "박신고", phone: "01012345678", relation: null },
      lastSeenLat: null,
      lastSeenLng: null,
      lastSeenAddress: "서울 서초구"
    }));
    const root = await mountView();

    setValue(root.querySelector('input[placeholder="예: 아들, 보호자, 지인"]'), "");
    setValue(fieldByTitle(root, "마지막 목격 위치"), "서울 서초구");
    buttonByText(root, "사건 정보 저장").click();
    await nextTick();
    buttonByText(root, "저장").click();
    await flushUi();

    expect(caseApi.updateCase).toHaveBeenCalledWith("17", {
      reporter: { relation: null },
      lastSeenAddress: "서울 서초구",
      lastSeenLat: null,
      lastSeenLng: null
    });
    expect(caseApi.putCasePhoto).not.toHaveBeenCalled();
  });

  it("저장 중 다른 사건으로 이동해도 이전 사진을 새 사건에 업로드하거나 화면을 덮지 않는다", async () => {
    routing.route.path = "/admin/cases/17/edit";
    routing.route.params = { caseId: "17" };
    const pendingUpdate = deferred();
    caseApi.getCase.mockImplementation((caseId) => Promise.resolve(
      caseId === "18"
        ? rawCase({ id: 18, caseNumber: "EFU-18", missingName: "두 번째 사건", photoUrl: null })
        : rawCase()
    ));
    caseApi.updateCase.mockReturnValue(pendingUpdate.promise);
    caseApi.putCasePhoto.mockResolvedValue({ photoUrl: "https://storage.example/17-new.jpg" });
    const root = await mountView();
    const selectedPhoto = choosePhoto(root, "case-17.png");
    setValue(fieldByTitle(root, "실종 경위", "textarea"), "첫 번째 사건 수정 중입니다.");

    buttonByText(root, "사건 정보 저장").click();
    await nextTick();
    buttonByText(root, "저장").click();
    await flushUi();
    expect(caseApi.updateCase).toHaveBeenCalledWith("17", { reportContent: "첫 번째 사건 수정 중입니다." });

    routing.route.path = "/admin/cases/18/edit";
    routing.route.params.caseId = "18";
    await flushUi();
    pendingUpdate.resolve(rawCase({ reportContent: "첫 번째 사건 수정 중입니다." }));
    await flushUi();

    expect(caseApi.putCasePhoto).toHaveBeenCalledWith("17", selectedPhoto);
    expect(caseApi.putCasePhoto).not.toHaveBeenCalledWith("18", expect.anything());
    expect(fieldByTitle(root, "이름").value).toBe("두 번째 사건");
    expect(fieldByTitle(root, "실종 경위", "textarea").value).not.toBe("첫 번째 사건 수정 중입니다.");
    expect(root.querySelector('[role="dialog"]')).toBeNull();
    expect(routing.router.push).not.toHaveBeenCalled();
  });

  it("종료 사건은 기본 수정과 교체를 막고 기존 사진 삭제는 허용한다", async () => {
    routing.route.path = "/admin/cases/17/edit";
    routing.route.params = { caseId: "17" };
    caseApi.getCase.mockResolvedValue(rawCase({ status: "CLOSED", closedAt: "2026-07-30T05:30:00Z" }));
    const pendingDelete = deferred();
    caseApi.deleteCasePhoto.mockReturnValue(pendingDelete.promise);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const root = await mountView();

    expect(buttonByText(root, "사건 정보 저장").disabled).toBe(true);
    expect(root.querySelector('input[type="file"]').disabled).toBe(true);
    buttonByText(root, "기존 사진 삭제").click();
    await nextTick();
    expect(buttonByText(root, "사건 정보 저장").disabled).toBe(true);
    expect(root.querySelector('input[type="file"]').disabled).toBe(true);
    pendingDelete.resolve(undefined);
    await flushUi();

    expect(caseApi.deleteCasePhoto).toHaveBeenCalledWith("17");
    expect(root.textContent).not.toContain("등록된 사진");
  });

  it("사진 삭제가 진행되는 동안 교체와 저장을 잠근다", async () => {
    routing.route.path = "/admin/cases/17/edit";
    routing.route.params = { caseId: "17" };
    caseApi.getCase.mockResolvedValue(rawCase());
    const pendingDelete = deferred();
    caseApi.deleteCasePhoto.mockReturnValue(pendingDelete.promise);
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const root = await mountView();

    expect(buttonByText(root, "사건 정보 저장").disabled).toBe(false);
    expect(root.querySelector('input[type="file"]').disabled).toBe(false);
    buttonByText(root, "기존 사진 삭제").click();
    await nextTick();

    expect(buttonByText(root, "사건 정보 저장").disabled).toBe(true);
    expect(root.querySelector('input[type="file"]').disabled).toBe(true);
    pendingDelete.resolve(undefined);
    await flushUi();
    expect(buttonByText(root, "사건 정보 저장").disabled).toBe(false);
  });
});
