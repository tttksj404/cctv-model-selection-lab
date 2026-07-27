<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { getCases } from "../api/mockApi";
import BasePagination from "../components/common/BasePagination.vue";
import StateBlock from "../components/common/StateBlock.vue";
import StatusBadge from "../components/common/StatusBadge.vue";

const router = useRouter();
const filters = reactive({ keyword: "", status: "all", assignee: "" });
const rows = ref([]);
const caseOptions = ref([]);
const loading = ref(true);
const caseDropdownOpen = ref(false);
const page = ref(1);
const pageSize = ref(10);
const totalPages = computed(() => Math.max(1, Math.ceil(rows.value.length / pageSize.value)));
const visible = computed(() => rows.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value));
const selectedCase = computed(() => caseOptions.value.find((item) => item.caseNumber === filters.keyword));
const sortClosedLast = (items) => [...items].sort((a, b) => Number(a.status === "closed") - Number(b.status === "closed"));
const load = async () => {
  loading.value = true;
  const [filteredCases, allCases] = await Promise.all([getCases(filters), getCases()]);
  rows.value = sortClosedLast(filteredCases);
  caseOptions.value = allCases;
  loading.value = false;
};
const selectCase = (caseItem) => {
  filters.keyword = caseItem?.caseNumber || "";
  caseDropdownOpen.value = false;
};
const reset = () => { filters.keyword = ""; filters.status = "all"; filters.assignee = ""; caseDropdownOpen.value = false; };
watch(() => [filters.keyword, filters.status, filters.assignee], () => {
  page.value = 1;
  load();
});
onMounted(load);
</script>

<template>
  <section class="content-panel">
    <div class="section-heading"><div><h2>사건 관리</h2><p>검색, 필터, 페이지 이동, 상세 이동을 지원합니다.</p></div><button class="primary-button" @click="router.push('/admin/cases/new')">신규 사건 등록</button></div>
    <div class="filter-bar cases-filter-bar">
      <label class="case-select-field">
        사건 번호
        <div class="case-picker">
          <button type="button" class="case-picker-trigger" @click="caseDropdownOpen = !caseDropdownOpen">
            {{ selectedCase?.caseNumber || "전체 사건" }}
          </button>
          <div v-if="caseDropdownOpen" class="case-picker-menu">
            <button type="button" class="case-picker-option" @click="selectCase()"><span>전체 사건</span></button>
            <button v-for="c in caseOptions" :key="c.id" type="button" class="case-picker-option" @click="selectCase(c)">
              <span>{{ c.caseNumber }}</span>
              <div class="case-hover-card">
                <strong>{{ c.name }}</strong>
                <span>{{ c.gender }} · {{ c.age }}세</span>
                <span>{{ c.lastSeenLocation }}</span>
                <span>{{ c.reportedAt }} 접수</span>
              </div>
            </button>
          </div>
        </div>
      </label>
      <label>상태<select v-model="filters.status"><option value="all">전체</option><option value="received">접수</option><option value="searching">탐색 중</option><option value="candidate_found">후보 발견</option><option value="closed">종료</option></select></label>
      <label>담당자<input v-model="filters.assignee" placeholder="김민준" /></label>
      <label class="page-size-field">페이지 크기<select v-model.number="pageSize"><option>10</option><option>20</option></select></label>
      <button class="reset-button" @click="reset">초기화</button>
    </div>
    <StateBlock :loading="loading" :empty="visible.length === 0">
      <div class="table-scroll">
        <table class="case-table">
          <thead><tr><th>사건 번호</th><th>사진</th><th>이름</th><th>성별</th><th>나이</th><th>신고 시각</th><th>목격 위치</th><th>상태</th><th>담당자</th><th></th></tr></thead>
          <tbody>
            <tr v-for="item in visible" :key="item.id">
              <td class="mono">{{ item.caseNumber }}</td><td><span class="thumb">{{ item.photo }}</span></td><td>{{ item.name }}</td><td>{{ item.gender }}</td><td>{{ item.age }}</td><td>{{ item.reportedAt }}</td><td>{{ item.lastSeenLocation }}</td><td><StatusBadge :status="item.status" /></td><td>{{ item.assignee }}</td><td><button class="ghost-button" @click="router.push(`/admin/cases/${item.id}`)">상세보기</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <BasePagination v-model:page="page" :total-pages="totalPages" :total-count="rows.length" />
    </StateBlock>
  </section>
</template>
