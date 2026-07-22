<script setup>
import { Bar } from "vue-chartjs";
import { BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale, Tooltip } from "chart.js";
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { getCases, getChartData, getDashboardSummary } from "../api/mockApi";
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
const page = ref(1);
const totalPages = computed(() => Math.max(1, Math.ceil(cases.value.length / 10)));
const visibleCases = computed(() => cases.value.slice((page.value - 1) * 10, page.value * 10));
const chartData = computed(() => ({
  labels: chart.value.map((item) => item.date),
  datasets: [
    { label: "신고 접수", data: chart.value.map((item) => item.reports), backgroundColor: "#4f8fcb", borderRadius: 5 },
    { label: "후보 탐지", data: chart.value.map((item) => item.candidates), backgroundColor: "#d7a642", borderRadius: 5 }
  ]
}));

onMounted(async () => {
  [summary.value, cases.value, chart.value] = await Promise.all([getDashboardSummary(), getCases(), getChartData(chartRange.value)]);
  loading.value = false;
});

const changeChartRange = async (range) => {
  chartRange.value = range;
  chart.value = await getChartData(range);
};
</script>

<template>
  <StateBlock :loading="loading">
    <section class="summary-grid">
      <SummaryCard v-for="item in summary" :key="item.id" :item="item" />
    </section>
    <section class="content-panel chart-panel">
      <div class="section-heading">
        <div><h2>사건 및 후보 탐지 현황</h2><p>기간 기준에 따라 신고 접수와 후보 탐지를 비교합니다.</p></div>
        <div class="segmented">
          <button :class="{ active: chartRange === '7d' }" @click="changeChartRange('7d')">7일</button>
          <button :class="{ active: chartRange === 'month' }" @click="changeChartRange('month')">한달</button>
        </div>
      </div>
      <div class="chart-box"><Bar :data="chartData" :options="{ responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } }, scales: { y: { beginAtZero: true } } }" /></div>
    </section>
    <section class="content-panel full-width-panel">
      <div>
        <div class="section-heading"><div><h2>최근 사건 목록</h2><p>행 클릭 시 사건 상세로 이동합니다.</p></div></div>
        <div class="table-scroll">
          <table class="case-table">
            <thead><tr><th>사건 번호</th><th>실종자</th><th>신고 시각</th><th>상태</th><th>담당자</th></tr></thead>
            <tbody>
              <tr v-for="item in visibleCases" :key="item.id" @click="router.push(`/admin/cases/${item.id}`)">
                <td class="mono">{{ item.caseNumber }}</td><td>{{ item.name }}</td><td>{{ item.reportedAt }}</td><td><StatusBadge :status="item.status" /></td><td>{{ item.assignee }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <BasePagination v-model:page="page" :total-pages="totalPages" :total-count="cases.length" />
      </div>
    </section>
  </StateBlock>
</template>
