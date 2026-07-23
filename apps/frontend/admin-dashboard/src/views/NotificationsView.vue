<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { getNotifications } from "../api/mockApi";
import BasePagination from "../components/common/BasePagination.vue";

const router = useRouter();
const rows = ref([]);
const type = ref("all");
const page = ref(1);
const pageSize = 5;
const filteredRows = computed(() => rows.value.filter((item) => type.value === "all" || item.type === type.value));
const totalPages = computed(() => Math.max(1, Math.ceil(filteredRows.value.length / pageSize)));
const visibleRows = computed(() => filteredRows.value.slice((page.value - 1) * pageSize, page.value * pageSize));
onMounted(async () => rows.value = await getNotifications());
const markAll = () => rows.value = rows.value.map((item) => ({ ...item, unread: false }));
watch(type, () => { page.value = 1; });
</script>

<template>
  <section class="content-panel notification-page">
    <div class="section-heading"><div><h2>알림</h2><p>알림 내역을 확인하고 수신 설정을 관리합니다.</p></div><div class="section-actions"><button class="ghost-button" @click="router.push('/admin/notifications/settings')">알림 설정</button><button class="primary-button" @click="markAll">전체 읽음</button></div></div>
    <div class="filter-bar"><label>알림 유형<select v-model="type"><option value="all">전체</option><option>실시간 후보 탐지</option><option>사건 상태 변경</option><option>CCTV 연결 없음</option><option>시스템 오류</option></select></label></div>
    <button v-for="n in visibleRows" :key="n.id" :class="['notification-line', n.unread && 'unread']" @click="router.push(n.route)"><span class="notification-time">{{ n.time }}</span><span class="notification-content"><strong>{{ n.title }}</strong><p>{{ n.message }}</p></span><span class="notification-type">{{ n.type }}</span></button>
    <BasePagination v-model:page="page" :total-pages="totalPages" :total-count="filteredRows.length" />
  </section>
</template>
