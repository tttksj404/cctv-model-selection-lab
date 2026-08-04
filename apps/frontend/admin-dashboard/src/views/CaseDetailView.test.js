import { createApp, nextTick } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const caseApi = vi.hoisted(() => ({
  addCaseCameras: vi.fn(),
  closeCase: vi.fn(),
  createSearchCondition: vi.fn(),
  deleteSearchCondition: vi.fn(),
  getCase: vi.fn(),
  listCaseCameras: vi.fn(),
  listSearchConditions: vi.fn(),
  removeCaseCamera: vi.fn(),
  replaceSearchCondition: vi.fn(),
  updateCaseStatus: vi.fn()
}));

vi.mock("../api/caseApi", () => caseApi);

import CaseDetailView from "./CaseDetailView.vue";

const rawCase = (overrides = {}) => ({
  id: 17,
  caseNumber: "EFU-0123456789ABCDEFGHJKMNPQRS",
  status: "RECEIVED",
  reporter: { id: 9, name: "홍길동", phone: "01012345678", relation: "보호자" },
  reportContent: "귀가하지 않아 신고했습니다.",
  missingName: "김민수",
  gender: "MALE",
  birthYear: 1952,
  appearance: { hair: "짧은 머리", upperClothing: "검은 셔츠" },
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

async function flushUi() {
  for (let index = 0; index < 8; index += 1) await Promise.resolve();
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

async function mountViewContext() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/admin/cases/:caseId", component: CaseDetailView },
      { path: "/admin/cases", component: { template: "<div>목록</div>" } }
    ]
  });
  await router.push("/admin/cases/17");
  await router.isReady();

  const root = document.createElement("div");
  document.body.append(root);
  const app = createApp(CaseDetailView).use(router);
  app.mount(root);
  mountedApps.push({ app, root });
  await flushUi();
  return { root, router };
}

async function mountView() {
  return (await mountViewContext()).root;
}

function buttonByText(root, text) {
  return [...root.querySelectorAll("button")].find((button) => button.textContent.trim() === text);
}

function modalButtonByText(root, text) {
  return [...root.querySelectorAll(".modal button")].find((button) => button.textContent.trim() === text);
}

async function inputModalReason(root, value) {
  const textarea = root.querySelector(".modal textarea");
  textarea.value = value;
  textarea.dispatchEvent(new Event("input", { bubbles: true }));
  await nextTick();
}

beforeEach(() => {
  vi.clearAllMocks();
  caseApi.listSearchConditions.mockResolvedValue([{
    id: 1,
    prompt: "a person wearing a blue short sleeve top and black pants",
    normalizedPrompt: "a person wearing a blue short sleeve top and black pants",
    normalizedExclusionPrompt: null,
    realtimeUsable: true
  }]);
  caseApi.listCaseCameras.mockResolvedValue([{
    id: 1,
    cameraId: 3,
    cameraCode: "CAM-003",
    cameraName: "3번 카메라",
    searchEnabled: true
  }]);
});

afterEach(() => {
  for (const { app, root } of mountedApps.splice(0)) {
    app.unmount();
    root.remove();
  }
});

describe("CaseDetailView", () => {
  it("실제 상세·사진을 표시하고 미구현 후보·동선은 빈 상태와 미배정으로 남긴다", async () => {
    caseApi.getCase.mockResolvedValue(rawCase());

    const root = await mountView();

    expect(caseApi.getCase).toHaveBeenCalledWith("17");
    expect(root.textContent).toContain("김민수");
    expect(root.textContent).toContain("홍길동(보호자) / 01012345678");
    expect(root.textContent).toContain("미배정");
    expect(root.textContent).toContain("확인된 동선이 없습니다.");
    expect(root.textContent).toContain("탐지된 후보가 없습니다.");
    expect(root.querySelector(".portrait img").getAttribute("src")).toBe("https://storage.example/photo.jpg");

    const options = [...root.querySelectorAll('select[aria-label="변경할 사건 상태"] option')]
      .map((option) => option.value);
    expect(options).toEqual(["searching"]);
    expect(root.textContent).toContain("현장 탐색");
  });

  it("사건 본문은 설정 조회 완료를 기다리지 않고 먼저 표시한다", async () => {
    const pendingConditions = deferred();
    const pendingCameras = deferred();
    caseApi.getCase.mockResolvedValue(rawCase());
    caseApi.listSearchConditions.mockReturnValue(pendingConditions.promise);
    caseApi.listCaseCameras.mockReturnValue(pendingCameras.promise);

    const root = await mountView();

    expect(root.textContent).toContain("김민수");
    expect(root.textContent).toContain("데이터를 불러오는 중입니다.");

    pendingConditions.resolve([]);
    pendingCameras.resolve([]);
    await flushUi();
    expect(root.textContent).toContain("등록된 탐색 조건이 없습니다.");
    expect(root.textContent).toContain("배정된 카메라가 없습니다.");
  });

  it("상태 변경 사유를 필수로 보내고 RECEIVED→SEARCHING 422를 안내한다", async () => {
    caseApi.getCase.mockResolvedValue(rawCase());
    caseApi.updateCaseStatus.mockRejectedValue({
      status: 422,
      code: "BUSINESS_RULE_VIOLATION",
      message: "탐색 조건과 활성 카메라가 필요합니다."
    });
    const root = await mountView();

    buttonByText(root, "상태 변경").click();
    await nextTick();
    const modalConfirm = modalButtonByText(root, "상태 변경");
    expect(modalConfirm.disabled).toBe(true);

    await inputModalReason(root, "탐색 개시");
    modalButtonByText(root, "상태 변경").click();
    await flushUi();

    expect(caseApi.updateCaseStatus).toHaveBeenCalledWith("17", {
      status: "SEARCHING",
      reason: "탐색 개시"
    });
    expect(root.textContent).toContain("탐색 조건과 활성 카메라가 필요합니다.");
  });

  it("상태 변경 422 시 외부에서 종료된 사건 상태를 다시 불러온다", async () => {
    caseApi.getCase
      .mockResolvedValueOnce(rawCase())
      .mockResolvedValueOnce(rawCase({ status: "CLOSED", closedAt: "2026-08-03T05:00:00Z" }));
    caseApi.updateCaseStatus.mockRejectedValue({
      status: 422,
      code: "BUSINESS_RULE_VIOLATION",
      message: "허용되지 않는 사건 상태 전이입니다."
    });
    const root = await mountView();

    buttonByText(root, "상태 변경").click();
    await nextTick();
    await inputModalReason(root, "탐색 개시");
    modalButtonByText(root, "상태 변경").click();
    await flushUi();

    expect(caseApi.getCase).toHaveBeenCalledTimes(2);
    expect(root.querySelector(".modal")).toBeNull();
    expect(root.textContent).toContain("사건 상태가 '종료' 상태로 변경되어 최신 정보를 불러왔습니다.");
    expect(root.textContent).toContain("종료 사건 · 읽기 전용");
  });

  it("실시간 사용 가능 조건이나 활성 카메라가 없으면 SEARCHING 전환을 UI에서 차단한다", async () => {
    caseApi.getCase.mockResolvedValue(rawCase());
    caseApi.listSearchConditions.mockResolvedValue([{
      id: 2,
      prompt: "해석할 수 없는 기존 문장",
      normalizedPrompt: null,
      realtimeUsable: false
    }]);
    caseApi.listCaseCameras.mockResolvedValue([]);
    const root = await mountView();

    buttonByText(root, "상태 변경").click();
    await nextTick();

    expect(root.querySelector(".modal")).toBeNull();
    expect(root.textContent).toContain("탐색을 시작하려면 실시간 사용 가능 조건과 활성 배정 카메라가 각각 하나 이상 필요합니다.");
    expect(root.textContent).toContain("조건 설정으로 이동");
    expect(root.textContent).toContain("카메라 설정으로 이동");
    expect(caseApi.updateCaseStatus).not.toHaveBeenCalled();
  });

  it("설정 mutation 422가 외부 종료를 알리면 사건을 재조회해 읽기 전용으로 바꾼다", async () => {
    vi.spyOn(globalThis, "confirm").mockReturnValue(true);
    caseApi.getCase
      .mockResolvedValueOnce(rawCase())
      .mockResolvedValueOnce(rawCase({ status: "CLOSED", closedAt: "2026-08-03T05:00:00Z" }));
    caseApi.removeCaseCamera.mockRejectedValue({
      status: 422,
      code: "BUSINESS_RULE_VIOLATION",
      message: "종료 사건은 설정을 변경할 수 없습니다."
    });
    const root = await mountView();

    buttonByText(root, "제외").click();
    await flushUi();

    expect(caseApi.getCase).toHaveBeenCalledTimes(2);
    expect(root.textContent).toContain("종료 사건 · 읽기 전용");
    expect(root.textContent).toContain("종료된 사건은 더 이상 상태를 변경할 수 없습니다.");
    expect(buttonByText(root, "카메라 추가")).toBeUndefined();
  });

  it("일반 종료 충돌 시 최신 정보를 다시 조회하고 두 번째 확인에서 force=true로 종료한다", async () => {
    caseApi.getCase.mockResolvedValue(rawCase({ status: "SEARCHING" }));
    caseApi.closeCase
      .mockRejectedValueOnce({
        status: 409,
        code: "CASE_CLOSE_CONFLICT",
        message: "미처리 후보 또는 실행 중인 작업이 있습니다."
      })
      .mockResolvedValueOnce({
        id: 17,
        status: "CLOSED",
        closedAt: "2026-07-30T08:30:00Z",
        updatedAt: "2026-07-30T08:30:00Z"
      });
    const root = await mountView();

    buttonByText(root, "사건 종료").click();
    await nextTick();
    await inputModalReason(root, "가족에게 인계 완료");
    modalButtonByText(root, "사건 종료").click();
    await flushUi();

    expect(caseApi.closeCase).toHaveBeenNthCalledWith(1, "17", {
      reason: "가족에게 인계 완료",
      force: false
    });
    expect(caseApi.getCase).toHaveBeenCalledTimes(2);
    expect(root.textContent).toContain("사건을 강제로 종료할까요?");

    modalButtonByText(root, "강제 종료").click();
    await flushUi();
    expect(caseApi.closeCase).toHaveBeenNthCalledWith(2, "17", {
      reason: "가족에게 인계 완료",
      force: true
    });
    expect(root.textContent).toContain("사건을 종료했습니다.");
  });

  it("404를 일반 로딩 오류와 구분한다", async () => {
    caseApi.getCase.mockRejectedValue({ status: 404, message: "사건을 찾을 수 없습니다." });

    const root = await mountView();

    expect(root.textContent).toContain("사건을 찾을 수 없습니다.");
    expect(root.textContent).toContain("사건 목록으로");
  });

  it("늦게 도착한 이전 사건 조회 응답이 새 사건 화면을 덮지 않는다", async () => {
    const firstCase = deferred();
    caseApi.getCase.mockImplementation((caseId) => (
      caseId === "17"
        ? firstCase.promise
        : Promise.resolve(rawCase({
          id: 18,
          caseNumber: "EFU-18",
          missingName: "두 번째 사건",
          photoUrl: null
        }))
    ));
    const { root, router } = await mountViewContext();

    await router.push("/admin/cases/18");
    await flushUi();
    expect(root.textContent).toContain("두 번째 사건");

    firstCase.resolve(rawCase({ missingName: "늦은 첫 번째 사건" }));
    await flushUi();
    expect(root.textContent).toContain("두 번째 사건");
    expect(root.textContent).not.toContain("늦은 첫 번째 사건");
  });

  it("늦게 도착한 이전 사건 설정 응답이 새 사건 설정을 덮지 않는다", async () => {
    const oldConditions = deferred();
    const oldCameras = deferred();
    caseApi.getCase.mockImplementation((caseId) => Promise.resolve(rawCase({
      id: Number(caseId),
      caseNumber: `EFU-${caseId}`,
      missingName: `${caseId}번 사건`
    })));
    caseApi.listSearchConditions.mockImplementation((caseId) => (
      caseId === "17" ? oldConditions.promise : Promise.resolve([{
        id: 18,
        prompt: "a woman wearing a red long sleeve top and black pants",
        normalizedPrompt: "a woman wearing a red long sleeve top and black pants",
        realtimeUsable: true
      }])
    ));
    caseApi.listCaseCameras.mockImplementation((caseId) => (
      caseId === "17" ? oldCameras.promise : Promise.resolve([{
        id: 18,
        cameraId: 18,
        cameraCode: "CAM-018",
        cameraName: "새 사건 카메라",
        searchEnabled: true
      }])
    ));
    const { root, router } = await mountViewContext();

    await router.push("/admin/cases/18");
    await flushUi();
    expect(root.textContent).toContain("a woman wearing a red long sleeve top and black pants");
    expect(root.textContent).toContain("새 사건 카메라");

    oldConditions.resolve([{
      id: 17,
      prompt: "a man wearing a blue short sleeve top and gray pants",
      normalizedPrompt: "a man wearing a blue short sleeve top and gray pants",
      realtimeUsable: true
    }]);
    oldCameras.resolve([{
      id: 17,
      cameraId: 17,
      cameraCode: "CAM-017",
      cameraName: "이전 사건 카메라",
      searchEnabled: true
    }]);
    await flushUi();

    expect(root.textContent).toContain("새 사건 카메라");
    expect(root.textContent).not.toContain("이전 사건 카메라");
    expect(root.textContent).not.toContain("a man wearing a blue short sleeve top and gray pants");
  });

  it("상태 변경 중 다른 사건으로 이동하면 이전 응답을 새 상세에 적용하지 않는다", async () => {
    const pendingStatus = deferred();
    caseApi.getCase.mockImplementation((caseId) => Promise.resolve(
      caseId === "18"
        ? rawCase({ id: 18, caseNumber: "EFU-18", missingName: "두 번째 사건" })
        : rawCase()
    ));
    caseApi.updateCaseStatus.mockReturnValue(pendingStatus.promise);
    const { root, router } = await mountViewContext();

    buttonByText(root, "상태 변경").click();
    await nextTick();
    await inputModalReason(root, "첫 사건 상태 변경");
    modalButtonByText(root, "상태 변경").click();
    await flushUi();

    await router.push("/admin/cases/18");
    await flushUi();
    expect(root.textContent).toContain("두 번째 사건");
    expect(root.querySelector(".modal")).toBeNull();

    pendingStatus.resolve({
      id: 17,
      status: "SEARCHING",
      closedAt: null,
      updatedAt: "2026-07-30T08:30:00Z"
    });
    await flushUi();
    expect(root.textContent).toContain("두 번째 사건");
    expect(root.textContent).not.toContain("접수에서 탐색 중 상태로 변경했습니다.");
  });

  it("종료 409 응답이면 상세를 다시 조회해 이미 종료된 최신 상태를 반영한다", async () => {
    caseApi.getCase
      .mockResolvedValueOnce(rawCase({ status: "SEARCHING" }))
      .mockResolvedValueOnce(rawCase({
        status: "CLOSED",
        closedAt: "2026-07-30T08:30:00Z"
      }));
    caseApi.closeCase.mockRejectedValue({
      status: 409,
      code: "CASE_ALREADY_CLOSED",
      message: "이미 종료된 사건입니다."
    });
    const root = await mountView();

    buttonByText(root, "사건 종료").click();
    await nextTick();
    await inputModalReason(root, "중복 종료 확인");
    modalButtonByText(root, "사건 종료").click();
    await flushUi();

    expect(caseApi.getCase).toHaveBeenCalledTimes(2);
    expect(root.textContent).toContain("다른 요청으로 사건 상태가 변경되어 최신 정보를 다시 불러왔습니다.");
    expect(root.textContent).toContain("종료된 사건은 더 이상 상태를 변경할 수 없습니다.");
    expect(buttonByText(root, "사진 관리")).toBeTruthy();
  });
});
