<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { LayoutGrid, Table2 } from "lucide-vue-next";
import { useRoute, useRouter } from "vue-router";
import { getCandidates, getCases } from "../api/mockApi";

const router = useRouter();
const route = useRoute();
const filters = reactive({ caseNumber: String(route.query.caseNumber || ""), review: "all", view: "card" });
const rows = ref([]);
const cases = ref([]);
const caseDropdownOpen = ref(false);

const selectedCase = computed(() => cases.value.find((item) => item.caseNumber === filters.caseNumber));
const visible = computed(() =>
  rows.value.filter((item) => (!filters.caseNumber || item.caseNumber.includes(filters.caseNumber)) && (filters.review === "all" || item.review === filters.review))
);

onMounted(async () => {
  [rows.value, cases.value] = await Promise.all([getCandidates(), getCases()]);
});

const selectCase = (caseItem) => {
  filters.caseNumber = caseItem.caseNumber;
  caseDropdownOpen.value = false;
};
</script>

<template>
  <section class="content-panel">
    <div class="section-heading">
      <div>
        <h2>후보 검토 목록</h2>
        <p>카드/테이블 보기 전환과 판정 상태 필터를 제공합니다.</p>
      </div>
      <div class="segmented view-toggle">
        <button :class="{ active: filters.view === 'card' }" title="카드 보기" aria-label="카드 보기" @click="filters.view = 'card'">
          <LayoutGrid :size="17" />
        </button>
        <button :class="{ active: filters.view === 'table' }" title="테이블 보기" aria-label="테이블 보기" @click="filters.view = 'table'">
          <Table2 :size="17" />
        </button>
      </div>
    </div>

    <div class="filter-bar candidate-filter-bar">
      <label class="case-select-field">
        사건
        <div class="case-picker">
          <button type="button" class="case-picker-trigger" @click="caseDropdownOpen = !caseDropdownOpen">
            {{ selectedCase?.caseNumber || "전체 사건" }}
          </button>
          <div v-if="caseDropdownOpen" class="case-picker-menu">
            <button v-for="c in cases" :key="c.id" type="button" class="case-picker-option" @click="selectCase(c)">
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
      <label>
        판정 상태
        <select v-model="filters.review">
          <option value="all">전체</option>
          <option value="pending">미판정</option>
          <option value="confirmed">대상 확정</option>
          <option value="hold">보류</option>
          <option value="rejected">제외</option>
        </select>
      </label>
    </div>

    <div v-if="filters.view === 'card'" class="candidate-grid">
      <button v-for="item in visible" :key="item.id" class="candidate-card" @click="router.push(`/admin/candidates/${item.id}`)">
        <span class="image-placeholder large">{{ item.image }}</span>
        <strong>{{ item.caseNumber }}</strong>
        <p>{{ item.camera }} · {{ item.detectedAt }}</p>
        <b>{{ item.similarity }}%</b>
      </button>
    </div>

    <div v-else class="table-scroll">
      <table class="case-table">
        <thead>
          <tr><th>사건</th><th>CCTV</th><th>탐지 시각</th><th>유사도</th><th>상태</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="item in visible" :key="item.id">
            <td>{{ item.caseNumber }}</td>
            <td>{{ item.camera }}</td>
            <td>{{ item.detectedAt }}</td>
            <td>{{ item.similarity }}%</td>
            <td>{{ item.review }}</td>
            <td><button class="ghost-button" @click="router.push(`/admin/candidates/${item.id}`)">상세 검토</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
