import { fetchAdminCandidates } from "./candidateApi";
import { listCameras } from "./cameraApi";
import { listCases } from "./caseApi";
import { mapCaseListItem } from "../domain/caseMapper";

const KST_TIME_ZONE = "Asia/Seoul";
const PAGE_SIZE = 100;
const SUMMARY_CASE_SORT = "reportedAt,desc";
const CHART_CASE_SORT = "reportedAt,asc";
const CHART_CANDIDATE_SORT = "lastDetectedAt,asc";

const KST_DATE_FORMATTER = new Intl.DateTimeFormat("en-CA", {
  timeZone: KST_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit"
});

function dateParts(date) {
  return Object.fromEntries(
    KST_DATE_FORMATTER.formatToParts(date)
      .filter(({ type }) => type !== "literal")
      .map(({ type, value }) => [type, value])
  );
}

function dateKey(date) {
  const parts = dateParts(date);
  return `${parts.year}-${parts.month}-${parts.day}`;
}

function shiftDateKey(value, amount) {
  const date = new Date(`${value}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + amount);
  return date.toISOString().slice(0, 10);
}

function periodFor(range) {
  const dayCount = range === "month" ? 30 : range === "today" ? 1 : 7;
  const end = dateKey(new Date());
  const start = shiftDateKey(end, -(dayCount - 1));
  const endExclusive = shiftDateKey(end, 1);

  return {
    dates: Array.from({ length: dayCount }, (_, index) => shiftDateKey(start, index)),
    from: `${start}T00:00:00+09:00`,
    to: `${endExclusive}T00:00:00+09:00`
  };
}

function countFromPage(result) {
  return Number(result.meta?.totalElements || 0);
}

async function fetchAllPages(fetchPage, params) {
  const firstPage = await fetchPage({ ...params, page: 0, size: PAGE_SIZE });
  const totalPages = Number(firstPage.meta?.totalPages || 0);
  if (totalPages <= 1) return firstPage.data || [];

  const remainingPages = await Promise.all(
    Array.from({ length: totalPages - 1 }, (_, index) =>
      fetchPage({ ...params, page: index + 1, size: PAGE_SIZE })
    )
  );

  return [firstPage, ...remainingPages].flatMap((page) => page.data || []);
}

function countByDate(rows, field) {
  return rows.reduce((counts, row) => {
    if (!row[field]) return counts;
    const key = dateKey(new Date(row[field]));
    counts.set(key, (counts.get(key) || 0) + 1);
    return counts;
  }, new Map());
}

export async function getDashboardSummary() {
  const today = periodFor("today");
  const [total, searching, candidateFound, todayReports, onlineCameras] = await Promise.all([
    listCases({ page: 0, size: 1, sort: SUMMARY_CASE_SORT }),
    listCases({ status: "SEARCHING", page: 0, size: 1, sort: SUMMARY_CASE_SORT }),
    listCases({ status: "CANDIDATE_FOUND", page: 0, size: 1, sort: SUMMARY_CASE_SORT }),
    listCases({
      reportedFrom: today.from,
      reportedTo: today.to,
      page: 0,
      size: 1,
      sort: SUMMARY_CASE_SORT
    }),
    listCameras({ status: "ONLINE", page: 0, size: 1 })
  ]);

  return [
    { id: "total", title: "전체 사건 수", value: countFromPage(total), delta: null },
    { id: "searching", title: "탐색 중 사건 수", value: countFromPage(searching), delta: null },
    { id: "candidate", title: "후보 발견 사건 수", value: countFromPage(candidateFound), delta: null },
    { id: "today", title: "오늘 접수 신고 수", value: countFromPage(todayReports), delta: null },
    { id: "cctv", title: "운영 중 CCTV 수", value: countFromPage(onlineCameras), delta: null }
  ];
}

export async function getCases({ page = 0, size = 10 } = {}) {
  const result = await listCases({ page, size, sort: SUMMARY_CASE_SORT });
  return {
    data: (result.data || []).map(mapCaseListItem),
    meta: result.meta
  };
}

export async function getChartData(range = "7d") {
  const period = periodFor(range);
  const [cases, candidates] = await Promise.all([
    fetchAllPages(listCases, {
      reportedFrom: period.from,
      reportedTo: period.to,
      sort: CHART_CASE_SORT
    }),
    fetchAllPages(
      (params) => fetchAdminCandidates(params).then(({ rows, meta }) => ({ data: rows, meta })),
      {
        detectedFrom: period.from,
        detectedTo: period.to,
        sort: CHART_CANDIDATE_SORT
      }
    )
  ]);

  const reportCounts = countByDate(cases, "reportedAt");
  const candidateCounts = countByDate(candidates, "lastDetectedAt");

  return period.dates.map((date) => ({
    date: date.slice(5),
    reports: reportCounts.get(date) || 0,
    candidates: candidateCounts.get(date) || 0
  }));
}
