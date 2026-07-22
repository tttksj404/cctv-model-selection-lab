<script setup>
import { onMounted, ref } from "vue";
import { getCases, getRoutePoints } from "../api/mockApi";
const cases = ref([]); const points = ref([]); const selected = ref("");
onMounted(async () => { cases.value = await getCases(); points.value = await getRoutePoints(); selected.value = cases.value[0]?.id; });
</script>
<template>
  <section class="route-layout">
    <article class="content-panel"><div class="section-heading"><div><h2>추정 동선</h2><p>Kakao Maps SDK 연동을 고려한 지도 패널입니다.</p></div><select v-model="selected"><option v-for="c in cases" :key="c.id" :value="c.id">{{ c.caseNumber }} · {{ c.name }}</option></select></div><div class="map-panel route-map">Kakao Maps · CCTV/후보 위치 마커 · 전체 경로 맞춤 보기</div></article>
    <aside class="content-panel"><h2>동선 목록</h2><div v-for="(p, index) in points" :key="p.time" class="timeline-item"><strong>{{ index + 1 }}. {{ p.time }} · {{ p.camera }}</strong><p>{{ p.location }} · {{ p.note }}</p><button class="ghost-button">동선 제외</button></div><button class="primary-button">동선 정보 공유</button></aside>
  </section>
</template>
