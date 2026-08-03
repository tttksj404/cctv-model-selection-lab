<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";
import { LayoutGrid, Table2 } from "lucide-vue-next";
import { useRoute, useRouter } from "vue-router";
import { fetchAdminCandidates } from "../api/candidateApi";
import { listCases } from "../api/caseApi";
import BasePagination from "../components/common/BasePagination.vue";
import { formatCandidateDate, reviewStatusLabel, reviewStatusTone, similarityPercent, similarityTone } from "../domain/candidateMapper";

const router = useRouter();
const route = useRoute();
const filters = reactive({ caseId: "", review: "all", view: "card" });
const rows = ref([]);
const cases = ref([]);
const caseDropdownOpen = ref(false);
const loading = ref(true);
const error = ref("");
const page = ref(1);
const pageSize = ref(20);
const totalPages = ref(1);
const totalCount = ref(0);
const selectedCase = computed(() => cases.value.find((item) => String(item.id) === String(filters.caseId)));
const listParams = () => ({
  caseId: filters.caseId || undefined,
  reviewStatus: filters.review === "all" ? undefined : filters.review.toUpperCase(),
  page: page.value - 1,
  size: pageSize.value,
  sort: "lastDetectedAt,desc"
});

const loadCases = async () => {
  const result = await listCases({ page: 0, size: 100, sort: "reportedAt,desc" });
  cases.value = (result.data || []).map((item) => ({
    id: item.id,
    caseNumber: item.caseNumber,
    name: item.missingName || item.name
  }));

  const initialCaseNumber = String(route.query.caseNumber || "");
  const initialCaseId = String(route.query.caseId || "");
  const initialCase = cases.value.find((item) => String(item.id) === initialCaseId)
    || cases.value.find((item) => item.caseNumber === initialCaseNumber);
  if (initialCase) filters.caseId = String(initialCase.id);
};

const load = async ({ showLoading = true } = {}) => {
  if (showLoading) loading.value = true;
  error.value = "";
  try {
    const result = await fetchAdminCandidates(listParams());
    rows.value = result.rows;
    totalPages.value = Math.max(1, result.meta?.totalPages || 1);
    totalCount.value = result.meta?.totalElements || 0;
  } catch (exception) {
    rows.value = [];
    totalPages.value = 1;
    totalCount.value = 0;
    error.value = exception.message || "후보 목록을 불러오지 못했습니다.";
  } finally {
    loading.value = false;
  }
};

let refreshTimer;
const refresh = () => {
  if (document.visibilityState === "hidden") return;
  return load({ showLoading: false });
};

const selectCase = (caseItem) => {
  filters.caseId = caseItem?.id ? String(caseItem.id) : "";
  caseDropdownOpen.value = false;
};

watch(() => [filters.caseId, filters.review, pageSize.value], () => {
  if (page.value !== 1) {
    page.value = 1;
    return;
  }
  load();
});
watch(page, load);

onMounted(async () => {
  try {
    await loadCases();
  } catch {
    cases.value = [];
  }
  await load();
  refreshTimer = window.setInterval(refresh, 5000);
});

onUnmounted(() => {
  if (refreshTimer) window.clearInterval(refreshTimer);
});
</script>

<template>
  <section class="content-panel">
    <div class="section-heading">
      <div><h2>후보 검출 목록</h2><p>실시간 후보 탐지 결과를 사건과 판정 상태 기준으로 확인합니다.</p></div>
      <div class="segmented view-toggle">
        <button :class="{ active: filters.view === 'card' }" title="카드 보기" aria-label="카드 보기" @click="filters.view = 'card'"><LayoutGrid :size="17" /></button>
        <button :class="{ active: filters.view === 'table' }" title="테이블 보기" aria-label="테이블 보기" @click="filters.view = 'table'"><Table2 :size="17" /></button>
      </div>
    </div>

    <div class="filter-bar candidate-filter-bar">
      <label class="case-select-field">사건
        <div class="case-picker">
          <button type="button" class="case-picker-trigger" @click="caseDropdownOpen = !caseDropdownOpen">{{ selectedCase?.caseNumber || "전체 사건" }}</button>
          <div v-if="caseDropdownOpen" class="case-picker-menu">
            <button type="button" class="case-picker-option" @click="selectCase()">전체 사건</button>
            <button v-for="caseItem in cases" :key="caseItem.id" type="button" class="case-picker-option" @click="selectCase(caseItem)">{{ caseItem.caseNumber }} · {{ caseItem.name || "이름 미등록" }}</button>
          </div>
        </div>
      </label>
      <label>판정 상태
        <select v-model="filters.review">
          <option value="all">전체</option>
          <option value="pending">미판정</option>
          <option value="kept">보류</option>
          <option value="confirmed">확정</option>
          <option value="rejected">제외</option>
        </select>
      </label>
      <label>페이지 크기
        <select v-model.number="pageSize"><option :value="20">20</option><option :value="50">50</option><option :value="100">100</option></select>
      </label>
    </div>

    <p v-if="loading" class="empty-state">후보 목록을 불러오는 중입니다.</p>
    <p v-else-if="error" class="error-message">{{ error }}</p>
    <p v-else-if="rows.length === 0" class="empty-state">조회된 후보가 없습니다.</p>
    <template v-else>
      <div v-if="filters.view === 'card'" class="candidate-grid">
        <button v-for="item in rows" :key="item.id" class="candidate-card" @click="router.push(`/admin/candidates/${item.id}`)">
          <img v-if="item.cropUrl" :src="item.cropUrl" alt="후보 캡처" />
          <span v-else class="image-placeholder large">이미지 없음</span>
          <strong>{{ item.caseNumber }}</strong>
          <p>{{ item.cameraCode }} · {{ formatCandidateDate(item.lastDetectedAt) }}</p>
          <p class="candidate-location">{{ item.cameraName || "카메라 위치 미등록" }} · track {{ item.trackId }}</p>
          <b :class="['similarity-score', similarityTone(item.bestSimilarity)]">{{ similarityPercent(item.bestSimilarity) }}%</b><span :class="['status-badge', reviewStatusTone(item.reviewStatus)]">{{ reviewStatusLabel(item.reviewStatus) }}</span>
        </button>
      </div>
      <div v-else class="table-scroll">
        <table class="case-table"><thead><tr><th>사건</th><th>CCTV</th><th>카메라</th><th>최근 탐지</th><th>유사도</th><th>상태</th><th></th></tr></thead>
          <tbody><tr v-for="item in rows" :key="item.id"><td>{{ item.caseNumber }}</td><td>{{ item.cameraCode }}</td><td>{{ item.cameraName || "-" }}</td><td>{{ formatCandidateDate(item.lastDetectedAt) }}</td><td :class="['similarity-score', similarityTone(item.bestSimilarity)]">{{ similarityPercent(item.bestSimilarity) }}%</td><td><span :class="['status-badge', reviewStatusTone(item.reviewStatus)]">{{ reviewStatusLabel(item.reviewStatus) }}</span></td><td><button class="ghost-button" @click="router.push(`/admin/candidates/${item.id}`)">상세 보기</button></td></tr></tbody>
        </table>
      </div>
      <BasePagination v-model:page="page" :total-pages="totalPages" :total-count="totalCount" />
    </template>
  </section>
</template>
