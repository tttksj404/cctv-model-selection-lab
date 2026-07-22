import { cases, chartSeries, notifications, summaryCards } from "../data/mockData";

const wait = (ms = 350) => new Promise((resolve) => setTimeout(resolve, ms));

export async function fetchDashboardData() {
  await wait();
  return { summaryCards, cases, notifications };
}

export async function fetchChartData(range = "7d") {
  await wait(180);
  return chartSeries[range] ?? chartSeries["7d"];
}
