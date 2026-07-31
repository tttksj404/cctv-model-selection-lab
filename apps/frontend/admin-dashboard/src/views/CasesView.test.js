import { createApp, nextTick } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { listCasesMock, mapCaseListItemMock, routerPushMock } = vi.hoisted(() => ({
  listCasesMock: vi.fn(),
  mapCaseListItemMock: vi.fn(),
  routerPushMock: vi.fn()
}));

vi.mock("../api/caseApi", () => ({
  listCases: listCasesMock
}));

vi.mock("../domain/caseMapper", () => ({
  mapCaseListItem: mapCaseListItemMock
}));

vi.mock("vue-router", () => ({
  useRouter: () => ({ push: routerPushMock })
}));

import CasesView from "./CasesView.vue";

const rawCase = (overrides = {}) => ({
  id: 1,
  caseNumber: "EFU-CASE-1",
  name: "홍길동",
  gender: "남",
  age: 30,
  photo: "사진 없음",
  reportedAt: "2026-07-30 10:00",
  lastSeenLocation: "서울특별시",
  status: "received",
  ...overrides
});

const result = (data = [], meta = {}) => ({
  data,
  meta: {
    page: 0,
    size: 10,
    totalElements: data.length,
    totalPages: data.length ? 1 : 0,
    sort: "reportedAt,desc",
    ...meta
  }
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
  for (let index = 0; index < 5; index += 1) {
    await Promise.resolve();
    await nextTick();
  }
};

const click = (element) => {
  element.dispatchEvent(new MouseEvent("click", { bubbles: true }));
};

describe("CasesView", () => {
  let app;
  let root;

  const mount = () => {
    root = document.createElement("div");
    document.body.appendChild(root);
    app = createApp(CasesView);
    app.mount(root);
  };

  beforeEach(() => {
    mapCaseListItemMock.mockImplementation((item) => item);
  });

  afterEach(() => {
    app?.unmount();
    root?.remove();
  });

  it("loads the first server page and renders response metadata", async () => {
    const item = rawCase();
    listCasesMock.mockResolvedValue(result([item], {
      totalElements: 21,
      totalPages: 3
    }));

    mount();
    await settle();

    expect(listCasesMock).toHaveBeenCalledWith({
      status: undefined,
      caseNumber: undefined,
      page: 0,
      size: 10,
      sort: "reportedAt,desc"
    });
    expect(mapCaseListItemMock).toHaveBeenCalledWith(item, 0, [item]);
    expect(root.textContent).toContain("EFU-CASE-1");
    expect(root.textContent).toContain("전체 21건");
    expect(root.textContent).toContain("1 / 3");
    expect(root.querySelector("input[disabled]").value).toBe("미배정");
  });

  it("converts screen pages and status filters to API parameters", async () => {
    listCasesMock
      .mockResolvedValueOnce(result([rawCase()], { totalElements: 12, totalPages: 2 }))
      .mockResolvedValueOnce(result([rawCase({ id: 2 })], { page: 1, totalElements: 12, totalPages: 2 }))
      .mockResolvedValueOnce(result([rawCase({ status: "searching" })]));

    mount();
    await settle();

    const nextButton = [...root.querySelectorAll("button")]
      .find((button) => button.textContent.includes("다음"));
    click(nextButton);
    await settle();

    expect(listCasesMock).toHaveBeenNthCalledWith(2, {
      status: undefined,
      caseNumber: undefined,
      page: 1,
      size: 10,
      sort: "reportedAt,desc"
    });

    const statusSelect = root.querySelector(".filter-bar select");
    statusSelect.value = "searching";
    statusSelect.dispatchEvent(new Event("change", { bubbles: true }));
    await settle();

    expect(listCasesMock).toHaveBeenNthCalledWith(3, {
      status: "SEARCHING",
      caseNumber: undefined,
      page: 0,
      size: 10,
      sort: "reportedAt,desc"
    });
  });

  it("ignores a stale response that resolves after a newer filter request", async () => {
    const oldRequest = deferred();
    listCasesMock
      .mockImplementationOnce(() => oldRequest.promise)
      .mockResolvedValueOnce(result([rawCase({ id: 2, caseNumber: "EFU-NEW" })]));

    mount();

    const statusSelect = root.querySelector(".filter-bar select");
    statusSelect.value = "closed";
    statusSelect.dispatchEvent(new Event("change", { bubbles: true }));
    await settle();

    expect(root.textContent).toContain("EFU-NEW");

    oldRequest.resolve(result([rawCase({ caseNumber: "EFU-STALE" })]));
    await settle();

    expect(root.textContent).toContain("EFU-NEW");
    expect(root.textContent).not.toContain("EFU-STALE");
  });

  it("shows a load error and retries from StateBlock", async () => {
    listCasesMock
      .mockRejectedValueOnce(new Error("사건 목록 오류"))
      .mockResolvedValueOnce(result([rawCase()]));

    mount();
    await settle();

    expect(root.textContent).toContain("사건 목록 오류");
    const retryButton = [...root.querySelectorAll("button")]
      .find((button) => button.textContent.includes("다시 시도"));
    click(retryButton);
    await settle();

    expect(listCasesMock).toHaveBeenCalledTimes(2);
    expect(root.textContent).toContain("EFU-CASE-1");
  });

  it("loads up to 100 case-number options once and reuses the cache", async () => {
    listCasesMock
      .mockResolvedValueOnce(result([rawCase()]))
      .mockResolvedValueOnce(result([rawCase({ id: 2, caseNumber: "EFU-OPTION" })], {
        size: 100
      }));

    mount();
    await settle();

    const trigger = root.querySelector(".case-picker-trigger");
    click(trigger);
    await settle();

    expect(listCasesMock).toHaveBeenNthCalledWith(2, {
      page: 0,
      size: 100,
      sort: "reportedAt,desc"
    });
    expect(root.textContent).toContain("EFU-OPTION");

    click(trigger);
    click(trigger);
    await settle();

    expect(listCasesMock).toHaveBeenCalledTimes(2);
  });
});
