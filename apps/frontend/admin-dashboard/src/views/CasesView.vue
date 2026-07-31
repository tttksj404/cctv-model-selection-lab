<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { listCases } from "../api/caseApi";
import BasePagination from "../components/common/BasePagination.vue";
import StateBlock from "../components/common/StateBlock.vue";
import StatusBadge from "../components/common/StatusBadge.vue";
import { mapCaseListItem } from "../domain/caseMapper";

const router = useRouter();
const filters = reactive({ keyword: "", status: "all" });
const rows = ref([]);
const caseOptions = ref([]);
const loading = ref(true);
const error = ref("");
const caseDropdownOpen = ref(false);
const caseOptionsLoading = ref(false);
const caseOptionsLoaded = ref(false);
const caseOptionsError = ref("");
const page = ref(1);
const pageSize = ref(10);
const totalPages = ref(1);
const totalCount = ref(0);
const selectedCase = computed(() => caseOptions.value.find((item) => item.caseNumber === filters.keyword));

let latestRequestId = 0;

const listParams = () => ({
  status: filters.status === "all" ? undefined : filters.status.toUpperCase(),
  caseNumber: filters.keyword.trim() || undefined,
  page: page.value - 1,
  size: pageSize.value,
  sort: "reportedAt,desc"
});

const errorMessage = (cause, fallback) => cause?.message || fallback;

const load = async () => {
  const requestId = ++latestRequestId;
  loading.value = true;
  error.value = "";

  try {
    const result = await listCases(listParams());
    if (requestId !== latestRequestId) return;

    rows.value = (result.data || []).map(mapCaseListItem);
    totalPages.value = Math.max(1, result.meta?.totalPages || 0);
    totalCount.value = result.meta?.totalElements || 0;
  } catch (cause) {
    if (requestId !== latestRequestId) return;

    rows.value = [];
    totalPages.value = 1;
    totalCount.value = 0;
    error.value = errorMessage(cause, "사건 목록을 불러오지 못했습니다.");
  } finally {
    if (requestId === latestRequestId) loading.value = false;
  }
};

const loadCaseOptions = async () => {
  if (caseOptionsLoaded.value || caseOptionsLoading.value) return;

  caseOptionsLoading.value = true;
  caseOptionsError.value = "";

  try {
    const result = await listCases({ page: 0, size: 100, sort: "reportedAt,desc" });
    caseOptions.value = (result.data || []).map(mapCaseListItem);
    caseOptionsLoaded.value = true;
  } catch (cause) {
    caseOptionsError.value = errorMessage(cause, "사건번호 목록을 불러오지 못했습니다.");
  } finally {
    caseOptionsLoading.value = false;
  }
};

const toggleCaseDropdown = () => {
  caseDropdownOpen.value = !caseDropdownOpen.value;
  if (caseDropdownOpen.value) loadCaseOptions();
};

const selectCase = (caseItem) => {
  filters.keyword = caseItem?.caseNumber || "";
  caseDropdownOpen.value = false;
};

const reset = () => {
  filters.keyword = "";
  filters.status = "all";
  caseDropdownOpen.value = false;
};

watch(() => [filters.keyword, filters.status, pageSize.value], () => {
  if (page.value !== 1) {
    page.value = 1;
    return;
  }
  load();
});

watch(page, load);
onMounted(load);
</script>

<template>
  <section class="content-panel">
    <div class="section-heading"><div><h2>사건 관리</h2><p>검색, 필터, 페이지 이동, 상세 이동을 지원합니다.</p></div><button class="primary-button" @click="router.push('/admin/cases/new')">신규 사건 등록</button></div>
    <div class="filter-bar cases-filter-bar">
      <label class="case-select-field">
        사건 번호
        <div class="case-picker">
          <button type="button" class="case-picker-trigger" @click="toggleCaseDropdown">
            {{ selectedCase?.caseNumber || filters.keyword || "전체 사건" }}
          </button>
          <div v-if="caseDropdownOpen" class="case-picker-menu">
            <button type="button" class="case-picker-option" @click="selectCase()"><span>전체 사건</span></button>
            <span v-if="caseOptionsLoading" class="case-picker-option">사건번호를 불러오는 중입니다.</span>
            <button v-else-if="caseOptionsError" type="button" class="case-picker-option" @click="loadCaseOptions">
              <span>{{ caseOptionsError }} 다시 시도</span>
            </button>
            <span v-else-if="caseOptionsLoaded && caseOptions.length === 0" class="case-picker-option">조회된 사건이 없습니다.</span>
            <template v-else>
              <button v-for="c in caseOptions" :key="c.id" type="button" class="case-picker-option" @click="selectCase(c)">
                <span>{{ c.caseNumber }}</span>
                <div class="case-hover-card">
                  <strong>{{ c.name }}</strong>
                  <span>{{ c.gender }} · {{ c.age }}세</span>
                  <span>{{ c.lastSeenLocation }}</span>
                  <span>{{ c.reportedAt }} 접수</span>
                </div>
              </button>
            </template>
          </div>
        </div>
      </label>
      <label>상태<select v-model="filters.status"><option value="all">전체</option><option value="received">접수</option><option value="searching">탐색 중</option><option value="candidate_found">후보 발견</option><option value="field_search">현장 탐색</option><option value="closed">종료</option></select></label>
      <label title="현재 사건 API는 담당자 정보를 제공하지 않습니다.">담당자<input value="미배정" disabled /><small>담당자 연동 전까지 필터를 사용할 수 없습니다.</small></label>
      <label class="page-size-field">페이지 크기<select v-model.number="pageSize"><option>10</option><option>20</option></select></label>
      <button class="reset-button" @click="reset">초기화</button>
    </div>
    <StateBlock :loading="loading" :error="error" :empty="rows.length === 0" @retry="load">
      <div class="table-scroll">
        <table class="case-table">
          <thead><tr><th>사건 번호</th><th>사진</th><th>이름</th><th>성별</th><th>나이</th><th>신고 시각</th><th>목격 위치</th><th>상태</th><th>담당자</th><th></th></tr></thead>
          <tbody>
            <tr v-for="item in rows" :key="item.id">
              <td class="mono">{{ item.caseNumber }}</td><td><span class="thumb">{{ item.photo }}</span></td><td>{{ item.name }}</td><td>{{ item.gender }}</td><td>{{ item.age }}</td><td>{{ item.reportedAt }}</td><td>{{ item.lastSeenLocation }}</td><td><span v-if="item.status === 'field_search'" class="status-badge green">현장 탐색</span><StatusBadge v-else :status="item.status" /></td><td>미배정</td><td><button class="ghost-button" @click="router.push(`/admin/cases/${item.id}`)">상세보기</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <BasePagination v-model:page="page" :total-pages="totalPages" :total-count="totalCount" />
    </StateBlock>
  </section>
</template>
