<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { getCases, getRoutePoints } from "../api/mockApi";
const cases = ref([]); const points = ref([]); const caseDropdownOpen = ref(false); const selectedCaseNumber = ref(""); const excludedPointTimes = ref([]); const excludeTarget = ref(null); const excludeModalOpen = ref(false);
const followMode = ref(false); const followIndex = ref(0); let followTimer;
const selectedCase = computed(() => cases.value.find((item) => item.caseNumber === selectedCaseNumber.value) || cases.value[0]);
const visiblePoints = computed(() => points.value);
const followedPoint = computed(() => visiblePoints.value[followIndex.value] || visiblePoints.value[0]);
onMounted(async () => { cases.value = await getCases(); points.value = await getRoutePoints(); selectedCaseNumber.value = cases.value[0]?.caseNumber || ""; });
const selectCase = (caseItem) => { selectedCaseNumber.value = caseItem.caseNumber; caseDropdownOpen.value = false; };
const requestExclude = (point) => { excludeTarget.value = point; excludeModalOpen.value = true; };
const excludePoint = () => {
  if (excludeTarget.value) excludedPointTimes.value.push(excludeTarget.value.time);
  excludeTarget.value = null;
  excludeModalOpen.value = false;
};
const includePoint = (point) => { excludedPointTimes.value = excludedPointTimes.value.filter((time) => time !== point.time); };
const toggleRouteFollow = () => {
  followMode.value = !followMode.value;
  if (!followMode.value) {
    window.clearInterval(followTimer);
    return;
  }
  followIndex.value = 0;
  followTimer = window.setInterval(() => {
    if (!visiblePoints.value.length) return;
    followIndex.value = (followIndex.value + 1) % visiblePoints.value.length;
  }, 2200);
};
onUnmounted(() => window.clearInterval(followTimer));
</script>
<template>
  <section class="route-layout">
    <article class="content-panel"><div class="section-heading"><label class="case-select-field route-case-selector"><span class="route-case-label">사건 선택</span><div class="case-picker"><button type="button" class="case-picker-trigger" @click="caseDropdownOpen = !caseDropdownOpen">{{ selectedCase?.caseNumber || "사건 선택" }}</button><div v-if="caseDropdownOpen" class="case-picker-menu"><button v-for="c in cases" :key="c.id" type="button" class="case-picker-option" @click="selectCase(c)"><span>{{ c.caseNumber }}</span><div class="case-hover-card"><strong>{{ c.name }}</strong><span>{{ c.gender }} · {{ c.age }}세</span><span>{{ c.lastSeenLocation }}</span><span>{{ c.reportedAt }} 접수</span></div></button></div></div></label><div class="route-follow-actions"><button class="route-follow-link" :class="{ active: followMode }" @click="toggleRouteFollow">{{ followMode ? "동선 따라가기 중지" : "동선 따라보기" }}</button><span>실종자 동선을 순서대로 확인합니다.</span></div></div><div class="map-panel route-map" :class="{ following: followMode }"><div class="route-map-copy"><strong>{{ followMode ? `${followedPoint?.camera || "CCTV"} 동선 따라보기` : "CCTV 동선 지도" }}</strong><span>{{ followedPoint?.location || "CCTV 포인트를 순서대로 표시합니다." }}</span></div><div class="route-map-points"><span v-for="(point, index) in visiblePoints" :key="point.time" :class="['route-map-point', index === followIndex && followMode && 'active']">{{ point.camera }}</span></div></div></article>
    <aside class="content-panel"><h2>동선 목록</h2><div v-for="(p, index) in visiblePoints" :key="p.time" :class="['timeline-item', excludedPointTimes.includes(p.time) && 'excluded', index === followIndex && followMode && 'following']"><strong>{{ index + 1 }}. {{ p.time }} · <span class="route-camera">{{ p.camera }}</span></strong><p>{{ p.location }} · {{ p.note }}</p><button v-if="!excludedPointTimes.includes(p.time)" class="ghost-button" @click="requestExclude(p)">동선 제외</button><button v-else class="route-include-button" @click="includePoint(p)">동선 추가</button></div><button class="primary-button route-share-button">동선 정보 공유</button></aside>
    <div v-if="excludeModalOpen" class="modal-backdrop" @click.self="excludeModalOpen = false"><section class="modal"><h3>동선을 제외할까요?</h3><p>{{ excludeTarget?.location }} 동선이 목록에서 제외됩니다.</p><div class="modal-actions"><button class="ghost-button" @click="excludeModalOpen = false">취소</button><button class="primary-button" @click="excludePoint">제외하기</button></div></section></div>
  </section>
</template>
