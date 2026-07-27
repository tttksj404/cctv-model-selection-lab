<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { getCameras } from "../api/mockApi";
import StatusBadge from "../components/common/StatusBadge.vue";
import BasePagination from "../components/common/BasePagination.vue";
const router = useRouter(); const filters = reactive({ keyword: "", status: "all" }); const rows = ref([]);
const page = ref(1); const pageSize = 10;
const totalPages = computed(() => Math.max(1, Math.ceil(rows.value.length / pageSize)));
const visibleCameras = computed(() => rows.value.slice((page.value - 1) * pageSize, page.value * pageSize));
const load = async () => rows.value = await getCameras(filters); watch(filters, () => { page.value = 1; load(); }); onMounted(load);
</script>
<template>
  <section class="content-panel"><div class="section-heading"><div><h2>CCTV 관리</h2><p>목록, 등록, 관리, 상태 테스트를 제공합니다.</p></div><button class="primary-button" @click="router.push('/admin/cameras/new')">CCTV 등록</button></div><div class="filter-bar"><label>검색<input v-model="filters.keyword" /></label><label>상태<select v-model="filters.status"><option value="all">전체</option><option value="online">정상</option><option value="unstable">연결 불안정</option><option value="offline">연결 없음</option></select></label></div><div class="table-scroll"><table class="case-table"><thead><tr><th>ID</th><th>이름</th><th>위치</th><th>위도</th><th>경도</th><th>구역</th><th>상태</th><th>마지막 연결</th><th>사용</th><th></th></tr></thead><tbody><tr v-for="c in visibleCameras" :key="c.id"><td>{{ c.id }}</td><td>{{ c.name }}</td><td>{{ c.address }}</td><td>{{ c.lat }}</td><td>{{ c.lng }}</td><td>{{ c.zone }}</td><td><StatusBadge :status="c.status" /></td><td>{{ c.lastHeartbeat }}</td><td>{{ c.active ? '사용' : '비활성' }}</td><td><button class="ghost-button" @click="router.push(`/admin/cameras/${c.id}/edit`)">관리</button></td></tr></tbody></table></div><BasePagination v-model:page="page" :total-pages="totalPages" :total-count="rows.length" /></section>
</template>
