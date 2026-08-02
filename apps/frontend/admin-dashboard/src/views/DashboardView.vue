<script setup>
import { Bar } from "vue-chartjs";
import { BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale, Tooltip } from "chart.js";
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { getCases, getChartData, getDashboardSummary } from "../api/dashboardApi";
import BasePagination from "../components/common/BasePagination.vue";
import StateBlock from "../components/common/StateBlock.vue";
import StatusBadge from "../components/common/StatusBadge.vue";
import SummaryCard from "../components/common/SummaryCard.vue";

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);
const router = useRouter();
const summary = ref([]);
const cases = ref([]);
const chart = ref([]);
const chartRange = ref("7d");
const loading = ref(true);
const error = ref("");
const dashboardReady = ref(false);
const pageLoading = ref(false);
const chartLoading = ref(false);
const pageError = ref("");
const chartError = ref("");
const page = ref(1);
const totalPages = ref(1);
const totalCount = ref(0);
let loadRequestId = 0;
let caseRequestId = 0;
let chartRequestId = 0;
let activeRequestCount = 0;
const visibleCases = computed(() => cases.value);
const initialLoading = computed(() => loading.value && !dashboardReady.value);
const chartData = computed(() => ({
  labels: chart.value.map((item) => item.date),
  datasets: [
    { label: "신고 접수", data: chart.value.map((item) => item.reports), backgroundColor: "#4f8fcb", borderRadius: 5 },
    { label: "후보 탐지", data: chart.value.map((item) => item.candidates), backgroundColor: "#d7a642", borderRadius: 5 }
  ]
}));

async function settleAll(promises) {
  const results = await Promise.allSettled(promises);
  const rejected = results.find((result) => result.status === "rejected");
  if (rejected) throw rejected.reason;
  return results.map((result) => result.value);
}

const applyCasePage = (result) => {
  cases.value = result.data || [];
  totalPages.value = Math.max(1, result.meta?.totalPages || 0);
  totalCount.value = result.meta?.totalElements || 0;
};

const startRequest = () => {
  activeRequestCount += 1;
  loading.value = true;
};

const finishRequest = () => {
  activeRequestCount = Math.max(0, activeRequestCount - 1);
  if (activeRequestCount === 0) loading.value = false;
};

const load = async () => {
  const requestId = ++loadRequestId;
  const currentCaseRequestId = ++caseRequestId;
  const currentChartRequestId = ++chartRequestId;
  dashboardReady.value = false;
  pageLoading.value = false;
  chartLoading.value = false;
  pageError.value = "";
  chartError.value = "";
  error.value = "";
  startRequest();

  try {
    const [summaryResult, caseResult, chartResult] = await settleAll([
      getDashboardSummary(),
      getCases({ page: page.value - 1, size: 10 }),
      getChartData(chartRange.value)
    ]);
    if (requestId !== loadRequestId) return;
    summary.value = summaryResult;
    if (currentCaseRequestId === caseRequestId) applyCasePage(caseResult);
    if (currentChartRequestId === chartRequestId) chart.value = chartResult;
    dashboardReady.value = true;
  } catch (cause) {
    if (requestId !== loadRequestId) return;
    summary.value = [];
    cases.value = [];
    chart.value = [];
    error.value = cause?.message || "대시보드 데이터를 불러오지 못했습니다.";
  } finally {
    finishRequest();
  }
};

const changePage = async () => {
  if (pageLoading.value || (loading.value && !dashboardReady.value)) return;
  const requestId = ++caseRequestId;
  pageLoading.value = true;
  pageError.value = "";
  error.value = "";
  startRequest();

  try {
    const result = await getCases({ page: page.value - 1, size: 10 });
    if (requestId === caseRequestId) applyCasePage(result);
  } catch (cause) {
    if (requestId === caseRequestId) {
      pageError.value = cause?.message || "최근 사건 목록을 불러오지 못했습니다.";
    }
  } finally {
    if (requestId === caseRequestId) pageLoading.value = false;
    finishRequest();
  }
};

onMounted(load);

const changeChartRange = async (range) => {
  if (chartLoading.value || (loading.value && !dashboardReady.value) || (chartRange.value === range && !chartError.value)) return;
  const requestId = ++chartRequestId;
  chartRange.value = range;
  chartLoading.value = true;
  chartError.value = "";
  error.value = "";
  startRequest();

  try {
    const result = await getChartData(range);
    if (requestId === chartRequestId && chartRange.value === range) {
      chart.value = result;
    }
  } catch (cause) {
    if (requestId === chartRequestId && chartRange.value === range) {
      chartError.value = cause?.message || "차트 데이터를 불러오지 못했습니다.";
    }
  } finally {
    if (requestId === chartRequestId) chartLoading.value = false;
    finishRequest();
  }
};
</script>

<template>
  <StateBlock :loading="initialLoading" :error="error" @retry="load">
    <section class="summary-grid">
      <SummaryCard v-for="item in summary" :key="item.id" :item="item" />
    </section>
    <section class="content-panel chart-panel">
      <div class="section-heading">
        <div><h2>사건 및 후보 탐지 현황</h2><p>기간 기준에 따라 신고 접수와 후보 탐지를 비교합니다.</p></div>
        <div class="segmented" role="group" aria-label="차트 기간 선택">
          <button type="button" :disabled="chartLoading" :aria-pressed="chartRange === '7d'" :class="{ active: chartRange === '7d' }" @click="changeChartRange('7d')">7일</button>
          <button type="button" :disabled="chartLoading" :aria-pressed="chartRange === 'month'" :class="{ active: chartRange === 'month' }" @click="changeChartRange('month')">한달</button>
        </div>
      </div>
      <div class="chart-box" aria-live="polite">
        <div v-if="chartLoading" class="state-view"><strong>차트 데이터를 불러오는 중입니다.</strong></div>
        <div v-else-if="chartError" class="state-view error"><strong>{{ chartError }}</strong><button type="button" @click="changeChartRange(chartRange)">다시 시도</button></div>
        <Bar v-else aria-label="기간별 신고 접수와 후보 탐지 건수 차트" :data="chartData" :options="{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } }, scales: { y: { beginAtZero: true } } }" />
      </div>
    </section>
    <section class="content-panel full-width-panel">
      <div>
        <div class="section-heading"><div><h2>최근 사건 목록</h2><p>행 클릭 시 사건 상세로 이동합니다.</p></div></div>
        <div v-if="pageLoading" class="state-view" aria-live="polite"><strong>최근 사건 목록을 불러오는 중입니다.</strong></div>
        <div v-else-if="pageError" class="state-view error" aria-live="polite"><strong>{{ pageError }}</strong><button type="button" @click="changePage">다시 시도</button></div>
        <div v-else class="table-scroll">
          <table class="case-table">
            <thead><tr><th>사건 번호</th><th>실종자</th><th>신고 시각</th><th>상태</th><th>담당자</th></tr></thead>
            <tbody>
              <tr
                v-for="item in visibleCases"
                :key="item.id"
                tabindex="0"
                role="link"
                @click="router.push(`/admin/cases/${item.id}`)"
                @keydown.enter="router.push(`/admin/cases/${item.id}`)"
                @keydown.space.prevent="router.push(`/admin/cases/${item.id}`)"
              >
                <td class="mono">{{ item.caseNumber }}</td><td>{{ item.name }}</td><td>{{ item.reportedAt }}</td><td><StatusBadge :status="item.status" /></td><td>{{ item.assignee }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <BasePagination v-model:page="page" :total-pages="totalPages" :total-count="totalCount" :disabled="pageLoading" @update:page="changePage" />
      </div>
    </section>
  </StateBlock>
</template>
