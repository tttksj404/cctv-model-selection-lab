<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { LayoutGrid, Table2 } from "lucide-vue-next";
import { useRoute, useRouter } from "vue-router";
import { fetchAdminCandidates, objectUrl } from "../api/candidateApi";

const router = useRouter();
const route = useRoute();
const filters = reactive({ caseNumber: String(route.query.caseNumber || ""), review: "all", view: "card" });
const rows = ref([]);
const cases = ref([]);
const caseDropdownOpen = ref(false);
const loading = ref(true);
const error = ref("");
const selectedCase = computed(() => cases.value.find((item) => item.caseNumber === filters.caseNumber));
const similarityPercent = (similarity) => Math.round(Number(similarity || 0) * 100);
const similarityTone = (similarity) => {
  const score = similarityPercent(similarity);
  return score >= 70 ? "high" : score >= 40 ? "medium" : "low";
};
const visible = computed(() => rows.value.filter((item) =>
  (!filters.caseNumber || item.caseNumber?.includes(filters.caseNumber)) &&
  (filters.review === "all" || item.reviewStatus?.toLowerCase() === filters.review)
));
const load = async () => {
  loading.value = true;
  error.value = "";
  try {
    const result = await fetchAdminCandidates({ size: 100, sort: "lastDetectedAt,desc" });
    rows.value = result.rows;
    cases.value = [...new Map(result.rows.map((item) => [item.caseId, { id: item.caseId, caseNumber: item.caseNumber, name: item.missingName }])).values()];
  } catch (exception) {
    error.value = exception.response?.data?.message || "후보 목록을 불러오지 못했습니다.";
  } finally {
    loading.value = false;
  }
};
onMounted(load);
const selectCase = (caseItem) => { filters.caseNumber = caseItem?.caseNumber || ""; caseDropdownOpen.value = false; };
</script>

<template>
  <section class="content-panel">
    <div class="section-heading"><div><h2>후보 검토 목록</h2><p>실시간 탐지 결과를 사건·카메라·유사도 기준으로 확인합니다.</p></div><div class="segmented view-toggle"><button :class="{ active: filters.view === 'card' }" title="카드 보기" aria-label="카드 보기" @click="filters.view = 'card'"><LayoutGrid :size="17" /></button><button :class="{ active: filters.view === 'table' }" title="테이블 보기" aria-label="테이블 보기" @click="filters.view = 'table'"><Table2 :size="17" /></button></div></div>
    <div class="filter-bar candidate-filter-bar"><label class="case-select-field">사건<div class="case-picker"><button type="button" class="case-picker-trigger" @click="caseDropdownOpen = !caseDropdownOpen">{{ selectedCase?.caseNumber || "전체 사건" }}</button><div v-if="caseDropdownOpen" class="case-picker-menu"><button type="button" class="case-picker-option" @click="selectCase()">전체 사건</button><button v-for="caseItem in cases" :key="caseItem.id" type="button" class="case-picker-option" @click="selectCase(caseItem)">{{ caseItem.caseNumber }} · {{ caseItem.name || "이름 미등록" }}</button></div></div></label><label>판정 상태<select v-model="filters.review"><option value="all">전체</option><option value="pending">미판정</option><option value="approved">확정</option><option value="rejected">제외</option></select></label></div>
    <p v-if="loading" class="empty-state">후보 목록을 불러오는 중입니다.</p><p v-else-if="error" class="error-message">{{ error }}</p><p v-else-if="visible.length === 0" class="empty-state">조회된 후보가 없습니다.</p>
    <div v-else-if="filters.view === 'card'" class="candidate-grid"><button v-for="item in visible" :key="item.id" class="candidate-card" @click="router.push(`/admin/candidates/${item.id}`)"><img v-if="objectUrl(item.cropObjectKey)" :src="objectUrl(item.cropObjectKey)" alt="후보 캡처" /><span v-else class="image-placeholder large">이미지 키<br />{{ item.cropObjectKey || "없음" }}</span><strong>{{ item.caseNumber }}</strong><p>{{ item.cameraCode }} · {{ item.lastDetectedAt }}</p><p class="candidate-location">{{ item.cameraName || "카메라 위치 미등록" }} · track {{ item.trackId }}</p><b :class="['similarity-score', similarityTone(item.bestSimilarity)]">{{ similarityPercent(item.bestSimilarity) }}%</b></button></div>
    <div v-else class="table-scroll"><table class="case-table"><thead><tr><th>사건</th><th>CCTV</th><th>카메라</th><th>최근 탐지</th><th>유사도</th><th>상태</th><th></th></tr></thead><tbody><tr v-for="item in visible" :key="item.id"><td>{{ item.caseNumber }}</td><td>{{ item.cameraCode }}</td><td>{{ item.cameraName || "-" }}</td><td>{{ item.lastDetectedAt }}</td><td :class="['similarity-score', similarityTone(item.bestSimilarity)]">{{ similarityPercent(item.bestSimilarity) }}%</td><td>{{ item.reviewStatus }}</td><td><button class="ghost-button" @click="router.push(`/admin/candidates/${item.id}`)">상세 검토</button></td></tr></tbody></table></div>
  </section>
</template>
