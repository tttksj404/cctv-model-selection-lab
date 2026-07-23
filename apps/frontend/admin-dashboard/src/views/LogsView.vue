<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { getAuditLogs } from "../api/mockApi";
import BasePagination from "../components/common/BasePagination.vue";
const logs = ref([]); const selected = ref(null); const filters = reactive({ type: "", actor: "", fromDate: "", fromTime: "", toDate: "", toTime: "" });
const page = ref(1); const pageSize = 10;
const filteredLogs = computed(() => logs.value.filter((log) => {
  const matchesType = !filters.type || filters.type === "전체" || log.type === filters.type;
  const matchesActor = !filters.actor || log.actor.toLowerCase().includes(filters.actor.toLowerCase());
  const logDate = new Date(`2026-${log.time.replace(" ", "T")}:00`);
  const from = filters.fromDate ? new Date(`${filters.fromDate}T${filters.fromTime || "00:00"}:00`) : null;
  const to = filters.toDate ? new Date(`${filters.toDate}T${filters.toTime || "23:59"}:59`) : null;
  return matchesType && matchesActor && (!from || logDate >= from) && (!to || logDate <= to);
}));
const totalPages = computed(() => Math.max(1, Math.ceil(filteredLogs.value.length / pageSize)));
const visibleLogs = computed(() => filteredLogs.value.slice((page.value - 1) * pageSize, page.value * pageSize));
const resetFilters = () => Object.assign(filters, { type: "", actor: "", fromDate: "", fromTime: "", toDate: "", toTime: "" });
watch(filters, () => { page.value = 1; }, { deep: true });
onMounted(async () => logs.value = await getAuditLogs());
</script>
<template>
  <section class="content-panel"><div class="section-heading"><div><h2>시스템 로그</h2><p>로그 상세는 모달로 확인합니다.</p></div></div><div class="filter-bar logs-filter-bar"><label>로그 종류<select v-model="filters.type"><option value="">전체</option><option>로그인</option><option>사건 상태 변경</option><option>후보 판정</option><option>시스템 오류</option></select></label><label>사용자<input v-model="filters.actor" /></label><label>시작 일시<div class="custom-datetime"><input v-model="filters.fromDate" type="date" /><input v-model="filters.fromTime" type="time" /></div></label><label>종료 일시<div class="custom-datetime"><input v-model="filters.toDate" type="date" /><input v-model="filters.toTime" type="time" /></div></label><button class="reset-button logs-search-button" @click="resetFilters">초기화</button></div><div class="table-scroll"><table class="case-table"><thead><tr><th>발생 시각</th><th>사용자</th><th>작업 유형</th><th>대상</th><th>결과</th><th>IP</th><th>로그 내용</th></tr></thead><tbody><tr v-for="log in visibleLogs" :key="log.id"><td>{{ log.time }}</td><td>{{ log.actor }}</td><td>{{ log.type }}</td><td>{{ log.target }}</td><td>{{ log.result }}</td><td>{{ log.ip }}</td><td class="log-detail-cell"><span class="log-preview" :title="log.detail">{{ log.detail }}</span><button class="ghost-button" @click="selected=log">상세보기</button></td></tr></tbody></table></div><BasePagination v-model:page="page" :total-pages="totalPages" :total-count="filteredLogs.length" /><div v-if="selected" class="modal-backdrop" @click.self="selected=null"><section class="modal log-detail-modal"><h3>로그 상세</h3><div class="log-detail-grid"><div><span>발생 시각</span><strong>{{ selected.time }}</strong></div><div><span>사용자</span><strong>{{ selected.actor }}</strong></div><div><span>작업 유형</span><strong>{{ selected.type }}</strong></div><div><span>대상</span><strong>{{ selected.target }}</strong></div><div><span>결과</span><strong>{{ selected.result }}</strong></div><div><span>IP</span><strong>{{ selected.ip }}</strong></div></div><div class="log-detail-content"><span>로그 내용</span><p>{{ selected.detail }}</p></div><button class="primary-button" @click="selected=null">확인</button></section></div></section>
</template>
