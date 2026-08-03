import { createApp, nextTick } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { listAuditLogsMock } = vi.hoisted(() => ({ listAuditLogsMock: vi.fn() }));

vi.mock("../api/auditLogApi", () => ({
  listAuditLogs: listAuditLogsMock
}));

import LogsView from "./LogsView.vue";

const rawLog = (overrides = {}) => ({
  id: 1,
  createdAt: "2026-08-02T01:00:00Z",
  adminId: 10,
  adminName: "Administrator",
  caseId: 20,
  actionType: "CASE_STATUS_CHANGED",
  targetType: "CASE",
  targetId: 20,
  beforeValue: { status: "RECEIVED" },
  afterValue: { status: "SEARCHING" },
  detail: { reason: "Begin search" },
  ...overrides
});

const result = (data = [rawLog()], meta = {}) => ({
  data,
  meta: { page: 0, size: 20, totalElements: data.length, totalPages: data.length ? 1 : 0, sort: "createdAt,desc", ...meta }
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

const inputValue = async (input, value) => {
  input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  await nextTick();
};

describe("LogsView", () => {
  let app;
  let root;

  const mount = () => {
    root = document.createElement("div");
    document.body.appendChild(root);
    app = createApp(LogsView);
    app.mount(root);
  };

  beforeEach(() => {
    listAuditLogsMock.mockReset();
    listAuditLogsMock.mockResolvedValue(result());
  });

  afterEach(() => {
    vi.useRealTimers();
    app?.unmount();
    root?.remove();
  });

  it("loads and renders a server page with audit fields", async () => {
    mount();
    await settle();

    expect(listAuditLogsMock).toHaveBeenCalledWith({
      actionType: undefined,
      actor: undefined,
      caseId: undefined,
      from: undefined,
      to: undefined,
      page: 0,
      size: 20,
      sort: "createdAt,desc"
    });
    expect(root.textContent).toContain("Administrator");
    expect(root.textContent).toContain("CASE_STATUS_CHANGED");
    expect(root.textContent).toContain("CASE #20");
  });

  it("resets to page one for filters and requests the next server page", async () => {
    vi.useFakeTimers();
    listAuditLogsMock
      .mockResolvedValueOnce(result([rawLog()], { totalElements: 21, totalPages: 2 }))
      .mockResolvedValue(result([rawLog({ id: 2 })], { page: 1, totalElements: 21, totalPages: 2 }));
    mount();
    await settle();

    root.querySelector(".pagination button:last-child").click();
    await settle();
    expect(listAuditLogsMock).toHaveBeenNthCalledWith(2, expect.objectContaining({ page: 1 }));

    const actionType = root.querySelector(".logs-filter-bar select");
    actionType.value = "CASE_UPDATED";
    actionType.dispatchEvent(new Event("change", { bubbles: true }));
    await settle();
    expect(listAuditLogsMock).toHaveBeenNthCalledWith(3, expect.objectContaining({
      actionType: "CASE_UPDATED",
      page: 0
    }));

    await inputValue(root.querySelectorAll(".logs-filter-bar input")[0], "Administrator");
    expect(listAuditLogsMock).toHaveBeenCalledTimes(3);
    vi.advanceTimersByTime(300);
    await settle();
    expect(listAuditLogsMock).toHaveBeenNthCalledWith(4, expect.objectContaining({
      actor: "Administrator",
      page: 0
    }));

    await inputValue(root.querySelectorAll(".logs-filter-bar input")[1], "20");
    expect(listAuditLogsMock).toHaveBeenCalledTimes(4);
    vi.advanceTimersByTime(300);
    await settle();
    expect(listAuditLogsMock).toHaveBeenNthCalledWith(5, expect.objectContaining({
      caseId: "20",
      page: 0
    }));
  });

  it("converts date-only filters to an inclusive start and next-day exclusive end", async () => {
    mount();
    await settle();

    const dateInputs = root.querySelectorAll(".logs-filter-bar input[type='date']");
    await inputValue(dateInputs[0], "2026-08-02");
    await inputValue(dateInputs[1], "2026-08-02");
    await settle();

    const lastParams = listAuditLogsMock.mock.calls.at(-1)[0];
    expect(lastParams.from).toBe(new Date("2026-08-02T00:00:00").toISOString());
    expect(lastParams.to).toBe(new Date("2026-08-03T00:00:00").toISOString());
  });

  it("shows loading, error, empty and detail states", async () => {
    const request = deferred();
    listAuditLogsMock.mockReturnValue(request.promise);
    mount();
    await nextTick();
    expect(root.textContent).toContain("데이터를 불러오는 중입니다.");

    request.reject(new Error("감사 로그 조회 실패"));
    await settle();
    expect(root.textContent).toContain("감사 로그 조회 실패");
    expect(root.querySelector(".state-view.error button")).not.toBeNull();

    listAuditLogsMock.mockResolvedValueOnce(result([]));
    root.querySelector(".state-view.error button").click();
    await settle();
    expect(root.textContent).toContain("조회된 데이터가 없습니다.");

    listAuditLogsMock.mockResolvedValueOnce(result());
    const actionType = root.querySelector(".logs-filter-bar select");
    actionType.value = "CASE_CREATED";
    actionType.dispatchEvent(new Event("change", { bubbles: true }));
    await settle();
    root.querySelector(".log-detail-cell .ghost-button").click();
    await nextTick();
    expect(root.textContent).toContain("RECEIVED");
    expect(root.textContent).toContain("SEARCHING");
    expect(root.textContent).toContain("Begin search");
  });

  it("ignores a stale response after a newer filter request", async () => {
    const oldRequest = deferred();
    listAuditLogsMock
      .mockImplementationOnce(() => oldRequest.promise)
      .mockResolvedValueOnce(result([rawLog({ id: 2, adminName: "New Administrator" })]));
    mount();

    const actionType = root.querySelector(".logs-filter-bar select");
    actionType.value = "CASE_UPDATED";
    actionType.dispatchEvent(new Event("change", { bubbles: true }));
    await settle();
    expect(root.textContent).toContain("New Administrator");

    oldRequest.resolve(result([rawLog({ adminName: "Stale Administrator" })]));
    await settle();
    expect(root.textContent).toContain("New Administrator");
    expect(root.textContent).not.toContain("Stale Administrator");
  });
});
