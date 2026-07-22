<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { getNotifications } from "../api/mockApi";
const router = useRouter(); const rows = ref([]); const type = ref("all"); onMounted(async () => rows.value = await getNotifications());
const markAll = () => rows.value = rows.value.map((item) => ({ ...item, unread: false }));
</script>
<template>
  <section class="content-panel"><div class="section-heading"><div><h2>알림</h2><p>읽음 처리, 삭제, 유형 필터, 관련 페이지 이동을 지원합니다.</p></div><button class="primary-button" @click="markAll">전체 읽음</button></div><div class="filter-bar"><label>알림 유형<select v-model="type"><option value="all">전체</option><option>실시간 후보 탐지</option><option>사건 상태 변경</option><option>CCTV 연결 없음</option><option>시스템 오류</option></select></label></div><button v-for="n in rows.filter(x => type==='all' || x.type===type)" :key="n.id" :class="['notification-line', n.unread && 'unread']" @click="router.push(n.route)"><strong>{{ n.title }}</strong><p>{{ n.message }}</p><span>{{ n.type }}</span></button></section>
</template>
