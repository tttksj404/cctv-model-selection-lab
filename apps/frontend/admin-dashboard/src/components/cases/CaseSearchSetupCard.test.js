import { createApp, h, nextTick, reactive } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const caseApi = vi.hoisted(() => ({
  addCaseCameras: vi.fn(),
  createSearchCondition: vi.fn(),
  deleteSearchCondition: vi.fn(),
  listCaseCameras: vi.fn(),
  listSearchConditions: vi.fn(),
  removeCaseCamera: vi.fn(),
  replaceSearchCondition: vi.fn()
}));
const cameraApi = vi.hoisted(() => ({ listCameras: vi.fn() }));

vi.mock("../../api/caseApi", () => caseApi);
vi.mock("../../api/cameraApi", () => cameraApi);

import CaseSearchSetupCard from "./CaseSearchSetupCard.vue";

const usableCondition = (overrides = {}) => ({
  id: 3,
  prompt: "a woman wearing a red long sleeve top and black pants",
  normalizedPrompt: "a woman wearing a red long sleeve top and black pants",
  exclusionPrompt: null,
  normalizedExclusionPrompt: null,
  realtimeUsable: true,
  searchStart: null,
  searchEnd: null,
  searchArea: null,
  ...overrides
});

const activeCamera = (overrides = {}) => ({
  id: 5,
  cameraId: 7,
  cameraCode: "CAM-007",
  cameraName: "로비 카메라",
  searchEnabled: true,
  ...overrides
});

const globalCamera = (overrides = {}) => ({
  id: 8,
  cameraCode: "CAM-008",
  cameraName: "후문 카메라",
  mediaServer: { id: 2, serverCode: "MEDIA-02", name: "후문 서버" },
  latitude: 37.5,
  longitude: 127.0,
  address: "후문",
  status: "OFFLINE",
  lastHeartbeat: null,
  ...overrides
});

const mountedApps = [];

async function flushUi() {
  for (let index = 0; index < 10; index += 1) await Promise.resolve();
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

async function mountCard(overrides = {}) {
  const state = reactive({
    caseId: 17,
    closed: false,
    conditions: [usableCondition()],
    cameras: [activeCamera()],
    loading: false,
    error: "",
    ...overrides
  });
  const readiness = [];
  const refreshRequests = [];
  const root = document.createElement("div");
  document.body.append(root);
  const app = createApp({
    setup() {
      return () => h(CaseSearchSetupCard, {
        ...state,
        onReadinessChange: (value) => readiness.push(value),
        onCaseRefreshRequested: () => refreshRequests.push(String(state.caseId))
      });
    }
  });
  app.mount(root);
  mountedApps.push({ app, root });
  await flushUi();
  return { root, state, readiness, refreshRequests };
}

function buttonByText(root, text) {
  return [...root.querySelectorAll("button")]
    .find((button) => button.textContent.trim() === text);
}

function setControl(control, value) {
  control.value = value;
  control.dispatchEvent(new Event(control.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
}

beforeEach(() => {
  vi.clearAllMocks();
  caseApi.listSearchConditions.mockResolvedValue([usableCondition()]);
  caseApi.listCaseCameras.mockResolvedValue([activeCamera()]);
  caseApi.createSearchCondition.mockResolvedValue(usableCondition());
  caseApi.replaceSearchCondition.mockResolvedValue(usableCondition());
  caseApi.removeCaseCamera.mockResolvedValue(undefined);
  caseApi.addCaseCameras.mockResolvedValue([activeCamera(), activeCamera({ id: 6, cameraId: 8 })]);
  cameraApi.listCameras.mockResolvedValue({
    data: [globalCamera()],
    meta: { page: 0, size: 10, totalElements: 1, totalPages: 1, sort: "cameraCode,asc" }
  });
});

afterEach(() => {
  vi.restoreAllMocks();
  for (const { app, root } of mountedApps.splice(0)) {
    app.unmount();
    root.remove();
  }
});

describe("CaseSearchSetupCard", () => {
  it("counts only realtime-usable conditions and active assignments", async () => {
    const { root, readiness } = await mountCard({
      conditions: [usableCondition(), usableCondition({
        id: 4,
        prompt: "빨간 옷을 입은 사람",
        normalizedPrompt: null,
        realtimeUsable: false
      })],
      cameras: [activeCamera(), activeCamera({ id: 6, cameraId: 9, searchEnabled: false })]
    });

    expect(root.textContent).toContain("실시간 사용 가능 조건1개");
    expect(root.textContent).toContain("활성 배정 카메라1대");
    expect(root.textContent).toContain("구조화 입력으로 수정해야 실시간 탐색에 사용할 수 있습니다.");
    expect(readiness.at(-1)).toMatchObject({
      usableConditionCount: 1,
      activeCameraCount: 1,
      ready: true
    });
  });

  it("creates a structured canonical condition with POST and no similarity threshold", async () => {
    const { root } = await mountCard({ conditions: [] });
    buttonByText(root, "조건 추가").click();
    await nextTick();

    const selects = root.querySelectorAll(".condition-form select");
    setControl(selects[0], "woman");
    setControl(selects[1], "red");
    setControl(selects[2], "long sleeve");
    setControl(selects[3], "black");
    const area = root.querySelector('.condition-form input[placeholder="예: 테헤란로 일대"]');
    setControl(area, " 테헤란로 ");
    await nextTick();

    expect(root.textContent).toContain("a woman wearing a red long sleeve top and black pants");
    buttonByText(root, "저장").click();
    await flushUi();

    expect(caseApi.createSearchCondition).toHaveBeenCalledOnce();
    expect(caseApi.createSearchCondition.mock.calls[0][0]).toBe("17");
    expect(caseApi.createSearchCondition.mock.calls[0][1]).toEqual({
      prompt: "a woman wearing a red long sleeve top and black pants",
      exclusionPrompt: null,
      searchStart: null,
      searchEnd: null,
      searchArea: "테헤란로"
    });
    expect(caseApi.createSearchCondition.mock.calls[0][1]).not.toHaveProperty("similarityThreshold");
    expect(caseApi.listSearchConditions).toHaveBeenCalledWith("17");
    expect(root.textContent).toContain("탐색 조건을 추가했습니다.");
  });

  it("preserves sub-second time and uses PUT when replacing a condition", async () => {
    const start = new Date(2026, 7, 3, 9, 20, 59).toISOString();
    const end = new Date(2026, 7, 3, 13, 20, 57).toISOString();
    const condition = usableCondition({ searchStart: start, searchEnd: end, searchArea: "기존 구역" });
    const { root } = await mountCard({ conditions: [condition] });

    buttonByText(root, "수정").click();
    await nextTick();
    const dateInputs = root.querySelectorAll('.condition-form input[type="datetime-local"]');
    expect(dateInputs[0].value).toMatch(/:59(?:\.000)?$/);
    expect(dateInputs[1].value).toMatch(/:57(?:\.000)?$/);
    expect(dateInputs[0].getAttribute("step")).toBe("0.001");
    buttonByText(root, "저장").click();
    await flushUi();

    expect(caseApi.replaceSearchCondition).toHaveBeenCalledOnce();
    const payload = caseApi.replaceSearchCondition.mock.calls[0][2];
    expect(caseApi.replaceSearchCondition.mock.calls[0].slice(0, 2)).toEqual(["17", 3]);
    expect(new Date(payload.searchStart).getSeconds()).toBe(59);
    expect(new Date(payload.searchEnd).getSeconds()).toBe(57);
  });

  it("searches and pages the global camera picker, warns for offline selection, and multi-adds", async () => {
    cameraApi.listCameras
      .mockResolvedValueOnce({
        data: [globalCamera({ id: 8 })],
        meta: { page: 0, size: 10, totalElements: 12, totalPages: 2, sort: "cameraCode,asc" }
      })
      .mockResolvedValueOnce({
        data: [globalCamera({ id: 9, cameraCode: "CAM-009" })],
        meta: { page: 1, size: 10, totalElements: 12, totalPages: 2, sort: "cameraCode,asc" }
      })
      .mockResolvedValueOnce({
        data: [globalCamera({ id: 10, cameraCode: "GATE-010" })],
        meta: { page: 0, size: 10, totalElements: 1, totalPages: 1, sort: "cameraCode,asc" }
      });
    const { root } = await mountCard({ cameras: [] });

    buttonByText(root, "카메라 추가").click();
    await flushUi();
    buttonByText(root, "다음").click();
    await flushUi();
    expect(cameraApi.listCameras).toHaveBeenNthCalledWith(2, expect.objectContaining({ page: 1 }));

    const search = root.querySelector('input[aria-label="카메라 검색"]');
    setControl(search, "GATE");
    buttonByText(root, "검색").click();
    await flushUi();
    expect(cameraApi.listCameras).toHaveBeenNthCalledWith(3, expect.objectContaining({
      search: "GATE",
      page: 0
    }));

    const checkbox = root.querySelector('input[aria-label="GATE-010 선택"]');
    checkbox.click();
    await nextTick();
    expect(root.textContent).toContain("연결 없음 또는 오류 상태인 카메라 1대를 선택했습니다.");
    buttonByText(root, "선택 1대 추가").click();
    await flushUi();

    expect(caseApi.addCaseCameras).toHaveBeenCalledWith("17", [10]);
    expect(caseApi.listCaseCameras).toHaveBeenCalledWith("17");
    expect(root.textContent).toContain("선택한 카메라를 사건에 추가했습니다.");
  });

  it("shows a camera-add API failure inside the open picker", async () => {
    caseApi.addCaseCameras.mockRejectedValue({
      status: 400,
      code: "VALIDATION_ERROR",
      message: "선택한 카메라를 추가할 수 없습니다."
    });
    const { root } = await mountCard({ cameras: [] });

    buttonByText(root, "카메라 추가").click();
    await flushUi();
    root.querySelector('input[aria-label="CAM-008 선택"]').click();
    await nextTick();
    buttonByText(root, "선택 1대 추가").click();
    await flushUi();

    const modal = root.querySelector(".camera-picker-modal");
    expect(modal).toBeTruthy();
    expect(modal.querySelector(".picker-operation-error").textContent)
      .toContain("선택한 카메라를 추가할 수 없습니다.");
  });

  it("emits a case refresh request for a 422 setup conflict", async () => {
    vi.spyOn(globalThis, "confirm").mockReturnValue(true);
    caseApi.removeCaseCamera.mockRejectedValue({
      status: 422,
      code: "BUSINESS_RULE_VIOLATION",
      message: "종료 사건은 설정을 변경할 수 없습니다."
    });
    const { root, refreshRequests } = await mountCard();

    buttonByText(root, "제외").click();
    await flushUi();

    expect(refreshRequests).toEqual(["17"]);
    expect(caseApi.listSearchConditions).toHaveBeenCalledWith("17");
    expect(root.textContent).toContain("종료 사건은 설정을 변경할 수 없습니다.");
  });

  it("blocks every other setup mutation while one mutation is pending", async () => {
    vi.spyOn(globalThis, "confirm").mockReturnValue(true);
    const pendingRemove = deferred();
    caseApi.removeCaseCamera.mockReturnValue(pendingRemove.promise);
    const { root } = await mountCard();

    buttonByText(root, "조건 추가").click();
    await nextTick();
    buttonByText(root, "제외").click();
    await nextTick();

    expect(buttonByText(root, "저장").disabled).toBe(true);
    expect(buttonByText(root, "조건 추가").disabled).toBe(true);
    expect(buttonByText(root, "카메라 추가").disabled).toBe(true);
    buttonByText(root, "저장").click();
    expect(caseApi.createSearchCondition).not.toHaveBeenCalled();

    pendingRemove.resolve();
    await flushUi();
    expect(root.textContent).toContain("카메라를 사건에서 제외했습니다.");
  });

  it("renders a closed case read-only while retaining invalid legacy rows", async () => {
    const { root } = await mountCard({
      closed: true,
      conditions: [usableCondition({
        prompt: "기존 자유 문장",
        normalizedPrompt: null,
        realtimeUsable: false
      })]
    });

    expect(root.textContent).toContain("종료 사건 · 읽기 전용");
    expect(root.textContent).toContain("기존 자유 문장");
    expect(buttonByText(root, "조건 추가")).toBeUndefined();
    expect(buttonByText(root, "카메라 추가")).toBeUndefined();
    expect(buttonByText(root, "수정")).toBeUndefined();
    expect(buttonByText(root, "제외")).toBeUndefined();
  });
});
