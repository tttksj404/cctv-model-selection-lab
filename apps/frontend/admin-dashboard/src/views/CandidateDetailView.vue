<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { fetchAdminCandidate, objectUrl } from "../api/candidateApi";
import { similarityPercent as toSimilarityPercent } from "../domain/candidateMapper";

const route = useRoute();
const router = useRouter();
const item = ref(null);
const loading = ref(true);
const error = ref("");
const similarityPercent = computed(() => toSimilarityPercent(item.value?.bestSimilarity));
const frameUrl = computed(() => objectUrl(item.value?.frameObjectKey));
const cropUrl = computed(() => objectUrl(item.value?.cropObjectKey));

onMounted(async () => {
  try {
    item.value = await fetchAdminCandidate(route.params.candidateId);
  } catch (exception) {
    error.value = exception.response?.data?.message || "후보 상세를 불러오지 못했습니다.";
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <p v-if="loading" class="empty-state">후보 상세를 불러오는 중입니다.</p>
  <p v-else-if="error" class="error-message">{{ error }}</p>
  <section v-else-if="item" class="detail-layout candidate-detail">
    <article class="content-panel candidate-review-panel"><div class="candidate-detail-header"><div><span class="eyebrow">후보 상세</span><h2>{{ item.caseNumber }}</h2></div><span class="similarity-pill similarity-score high">AI 유사도 {{ similarityPercent }}%</span></div><div class="review-compare-grid"><div><span class="review-label">후보 캡처</span><div class="review-image capture"><img v-if="cropUrl" :src="cropUrl" alt="후보 crop" /><span v-else class="image-placeholder large">{{ item.cropObjectKey || "crop 이미지 키 없음" }}</span></div></div><div><span class="review-label">원본 프레임</span><div class="review-image"><img v-if="frameUrl" :src="frameUrl" alt="탐지 원본 프레임" /><span v-else class="image-placeholder large">{{ item.frameObjectKey || "frame 이미지 키 없음" }}</span></div></div></div></article>
    <aside class="candidate-side-stack"><article class="content-panel candidate-info-panel"><h2>후보 정보</h2><div class="candidate-info-list"><span><small>사건 번호</small><strong>{{ item.caseNumber }}</strong></span><span><small>실종자</small><strong>{{ item.missingName || "-" }}</strong></span><span><small>CCTV</small><strong>{{ item.cameraCode }}</strong></span><span><small>Track ID</small><strong>{{ item.trackId }}</strong></span><span><small>최근 탐지</small><strong>{{ item.lastDetectedAt }}</strong></span><span><small>탐지 횟수</small><strong>{{ item.detectionCount }}</strong></span><span><small>평균 유사도</small><strong>{{ Math.round(Number(item.averageSimilarity || 0) * 100) }}%</strong></span><span><small>상태</small><strong>{{ item.reviewStatus }}</strong></span></div></article><article class="content-panel"><h2>탐지 이력</h2><div v-if="item.detections?.length" class="table-scroll"><table class="case-table"><thead><tr><th>시각</th><th>이벤트</th><th>유사도</th><th>Crop key</th></tr></thead><tbody><tr v-for="detection in item.detections" :key="detection.eventId + detection.detectedAt"><td>{{ detection.detectedAt }}</td><td>{{ detection.eventId }}</td><td>{{ Math.round(Number(detection.similarity || 0) * 100) }}%</td><td>{{ detection.cropObjectKey }}</td></tr></tbody></table></div><p v-else class="empty-state">탐지 이력이 없습니다.</p></article><button class="ghost-button" @click="router.push('/admin/candidates')">목록으로</button></aside>
  </section>
</template>
