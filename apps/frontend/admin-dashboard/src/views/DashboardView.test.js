import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick } from "vue";

const { getCasesMock, getChartDataMock, getDashboardSummaryMock } = vi.hoisted(() => ({
  getCasesMock: vi.fn(),
  getChartDataMock: vi.fn(),
  getDashboardSummaryMock: vi.fn()
}));

vi.mock("../api/dashboardApi", () => ({
  getCases: getCasesMock,
  getChartData: getChartDataMock,
  getDashboardSummary: getDashboardSummaryMock
}));
vi.mock("vue-chartjs", () => ({ Bar: { render: () => null } }));
vi.mock("chart.js", () => ({
  BarElement: {},
  CategoryScale: {},
  Chart: { register: vi.fn() },
  Legend: {},
  LinearScale: {},
  Tooltip: {}
}));
vi.mock("vue-router", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import DashboardView from "./DashboardView.vue";

const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

const flushPromises = async () => {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await nextTick();
};

const casePage = (page) => ({
  data: [{ id: page + 1, caseNumber: `CASE-${page + 1}`, name: "홍길동", reportedAt: "2026-07-31 11:00", status: "searching", assignee: "미배정" }],
  meta: { totalPages: 2, totalElements: 2, page, size: 10 }
});

describe("DashboardView request states", () => {
  let app;
  let root;

  beforeEach(() => {
    getDashboardSummaryMock.mockResolvedValue([{ id: "total", title: "전체 사건 수", value: 2, delta: null }]);
    getChartDataMock.mockResolvedValue([{ date: "07-31", reports: 1, candidates: 1 }]);
    root = document.createElement("div");
    document.body.appendChild(root);
  });

  afterEach(() => {
    app?.unmount();
    root.remove();
    vi.clearAllMocks();
  });

  it("prevents duplicate page requests and clears the previous page error", async () => {
    const pageRequest = deferred();
    const retryRequest = deferred();
    let initialPageCall = true;
    getCasesMock.mockImplementation(({ page }) => {
      if (page === 0) {
        if (initialPageCall) {
          initialPageCall = false;
          return Promise.resolve(casePage(0));
        }
        return retryRequest.promise;
      }
      return pageRequest.promise;
    });

    app = createApp(DashboardView);
    app.mount(root);
    await flushPromises();

    const nextButton = root.querySelector(".pagination button:last-child");
    nextButton.click();
    await nextTick();

    expect(getCasesMock).toHaveBeenCalledTimes(2);
    expect(nextButton.disabled).toBe(true);
    expect(root.textContent).toContain("최근 사건 목록을 불러오는 중입니다.");

    nextButton.click();
    await nextTick();
    expect(getCasesMock).toHaveBeenCalledTimes(2);

    pageRequest.reject(new Error("페이지 조회 실패"));
    await flushPromises();
    expect(root.textContent).toContain("페이지 조회 실패");

    root.querySelector(".pagination button:nth-of-type(1)").click();
    await nextTick();
    expect(root.textContent).not.toContain("페이지 조회 실패");
    expect(root.textContent).toContain("최근 사건 목록을 불러오는 중입니다.");

    retryRequest.resolve(casePage(0));
    await flushPromises();
  });

  it("shows loading feedback while the chart range request is pending", async () => {
    const chartRequest = deferred();
    getCasesMock.mockResolvedValue(casePage(0));
    getChartDataMock.mockImplementation((range) => range === "month" ? chartRequest.promise : Promise.resolve([]));

    app = createApp(DashboardView);
    app.mount(root);
    await flushPromises();

    root.querySelector(".segmented button:last-child").click();
    await nextTick();

    expect(root.textContent).toContain("차트 데이터를 불러오는 중입니다.");

    chartRequest.resolve([{ date: "07-31", reports: 2, candidates: 3 }]);
    await flushPromises();
    expect(root.textContent).not.toContain("차트 데이터를 불러오는 중입니다.");
  });

  it("prevents a second chart range request while the current request is pending", async () => {
    const chartRequest = deferred();
    getCasesMock.mockResolvedValue(casePage(0));
    getChartDataMock.mockImplementation((range) => range === "month" ? chartRequest.promise : Promise.resolve([]));

    app = createApp(DashboardView);
    app.mount(root);
    await flushPromises();

    const sevenDayButton = root.querySelector(".segmented button:nth-of-type(1)");
    const monthButton = root.querySelector(".segmented button:nth-of-type(2)");
    monthButton.click();
    await nextTick();

    expect(getChartDataMock).toHaveBeenCalledTimes(2);
    expect(sevenDayButton.disabled).toBe(true);
    expect(monthButton.disabled).toBe(true);

    sevenDayButton.click();
    await nextTick();
    expect(getChartDataMock).toHaveBeenCalledTimes(2);

    chartRequest.resolve([{ date: "07-31", reports: 2, candidates: 3 }]);
    await flushPromises();
    expect(monthButton.disabled).toBe(false);
  });
});
