import { auditLogs, candidates, cases, chartSeries, dashboardSummary, monthlyChartSeries, notifications, routePoints, scanJobs, users } from "../mocks/mockData";

const wait = (ms = 220) => new Promise((resolve) => setTimeout(resolve, ms));
const includes = (value, keyword) => String(value).toLowerCase().includes(String(keyword).toLowerCase());

export async function getDashboardSummary() { await wait(); return dashboardSummary; }
export async function getChartData(range = "7d") { await wait(); return range === "month" ? monthlyChartSeries : chartSeries; }
export async function getNotifications() { await wait(); return notifications; }
export async function getCases(params = {}) {
  await wait();
  return cases.filter((item) => {
    const keyword = params.keyword ? includes(item.caseNumber, params.keyword) || includes(item.name, params.keyword) : true;
    const status = !params.status || params.status === "all" || item.status === params.status;
    const assignee = !params.assignee || includes(item.assignee, params.assignee);
    return keyword && status && assignee;
  });
}
export async function getCaseDetail(caseId) { await wait(); return cases.find((item) => item.id === caseId) ?? cases[0]; }
export async function createCase(data) { await wait(); return { id: "new-case", caseNumber: "CASE-2026-0418", ...data }; }
export async function updateCaseStatus(caseId, data) { await wait(); return { caseId, ...data }; }
export async function getCandidates(params = {}) {
  await wait();
  return candidates.filter((item) => {
    const caseMatch = !params.caseNumber || includes(item.caseNumber, params.caseNumber);
    const reviewMatch = !params.review || params.review === "all" || item.review === params.review;
    return caseMatch && reviewMatch;
  });
}
export async function reviewCandidate(candidateId, data) { await wait(); return { candidateId, ...data }; }
export async function getScanJobs() { await wait(); return scanJobs; }
export async function getRoutePoints() { await wait(); return routePoints; }
export async function getAuditLogs() { await wait(); return auditLogs; }
export async function getUsers() { await wait(); return users; }
