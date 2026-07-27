<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { getCandidates, getCaseDetail, getRoutePoints, reviewCandidate, updateCaseStatus } from "../api/mockApi";
import ConfirmModal from "../components/common/ConfirmModal.vue";
import StatusBadge from "../components/common/StatusBadge.vue";

const route = useRoute();
const router = useRouter();
const item = ref(null);
const candidates = ref([]);
const points = ref([]);
const nextStatus = ref("searching");
const modalOpen = ref(false);
const selectedCandidate = ref(null);
const reviewDecision = ref("confirmed");
const reviewReason = ref("");
const candidateImages = ["/mock/cctv-candidate-1.png", "/mock/cctv-candidate-2.png", "/mock/cctv-candidate-3.png"];
const selectedCandidateImage = computed(() => {
  const index = candidates.value.findIndex((candidate) => candidate.id === selectedCandidate.value?.id);
  return candidateImages[Math.max(0, index) % candidateImages.length];
});
const statusSteps = [
  { value: "received", label: "접수" },
  { value: "preparing", label: "탐색 준비" },
  { value: "searching", label: "탐색 중" },
  { value: "candidate_found", label: "후보 발견" },
  { value: "closed", label: "종료" }
];
const orderedPoints = computed(() => [...points.value].reverse());
const similarityTone = (similarity) => similarity >= 70 ? "high" : similarity >= 40 ? "medium" : "low";
onMounted(async () => {
  item.value = await getCaseDetail(route.params.caseId);
  nextStatus.value = item.value.status;
  candidates.value = await getCandidates({ caseNumber: item.value.caseNumber });
  points.value = await getRoutePoints();
});
const changeStatus = async () => {
  await updateCaseStatus(item.value.id, { status: nextStatus.value });
  item.value.status = nextStatus.value;
  modalOpen.value = false;
};
const openCandidateModal = (candidate) => {
  selectedCandidate.value = candidate;
  reviewDecision.value = candidate.review === "rejected" ? "rejected" : candidate.review === "hold" ? "hold" : "confirmed";
  reviewReason.value = "";
};
const closeCandidateModal = () => {
  selectedCandidate.value = null;
};
const submitCandidateReview = async () => {
  if (!selectedCandidate.value) return;
  await reviewCandidate(selectedCandidate.value.id, { review: reviewDecision.value, reason: reviewReason.value });
  selectedCandidate.value.review = reviewDecision.value;
  if (reviewDecision.value === "confirmed") {
    item.value.status = "candidate_found";
    nextStatus.value = "candidate_found";
  }
  closeCandidateModal();
};
</script>

<template>
  <section v-if="item" class="detail-layout">
    <div class="case-detail-main">
      <article class="content-panel">
        <div class="section-heading case-detail-heading">
          <div><p class="mono">{{ item.caseNumber }}</p><h2>{{ item.name }}</h2></div>
          <div class="status-flow case-status-steps">
            <span v-for="step in statusSteps" :key="step.value" :class="{ active: item.status === step.value }">{{ step.label }}</span>
          </div>
        </div>
        <div class="profile-block"><div class="portrait"><img src="/mock/missing-person.png" alt="실종자 기준 사진" /></div><div class="info-grid"><span>성별/나이<strong>{{ item.gender }} · {{ item.age }}</strong></span><span>신고자<strong>{{ item.reporter }}</strong></span><span>신고 시간<strong>{{ item.reportedAt }}</strong></span><span>마지막 목격<strong>{{ item.lastSeenAt }}</strong></span><span>목격 위치<strong>{{ item.lastSeenLocation }}</strong></span><span>담당자<strong>{{ item.assignee }}</strong></span><span class="info-wide">인상착의<strong>{{ item.appearance }}</strong></span><span class="profile-action"><button class="ghost-button" @click="router.push(`/admin/cases/${item.id}/edit`)">사건 정보 수정</button></span></div></div>
        <div class="section-heading status-change-heading"><div><h2>상태 변경</h2><p>변경 사유 입력 모달을 거쳐 상태를 변경합니다.</p></div><div class="status-actions"><select v-model="nextStatus"><option value="received">접수</option><option value="preparing">탐색 준비</option><option value="searching">탐색 중</option><option value="candidate_found">후보 발견</option><option value="closed">종료</option></select><button class="primary-button" @click="modalOpen=true">변경</button></div></div>
      </article>
      <article class="content-panel"><h2>추정 동선</h2><div class="map-panel case-route-map"><div class="route-map-copy"><strong>Kakao Maps</strong><span>탐지된 CCTV 위치를 시간순으로 표시합니다.</span></div><div class="case-map-points"><span v-for="(point, index) in orderedPoints" :key="point.time" :style="{ left: `${12 + index * 23}%`, top: `${66 - index * 13}%` }">{{ index + 1 }}</span></div></div><div v-for="(point, index) in orderedPoints" :key="point.time" :class="['timeline-item', index === 0 && 'latest']"><div class="timeline-meta"><time>{{ point.time }}</time><strong>{{ point.camera }}</strong></div><p>{{ point.location }} · {{ point.note }}</p></div></article>
    </div>
    <article class="content-panel"><h2>후보 탐지 목록</h2><button v-for="(cand, index) in candidates" :key="cand.id" class="candidate-row detail-candidate" @click="openCandidateModal(cand)"><span class="image-placeholder"><img :src="candidateImages[index % candidateImages.length]" :alt="`${cand.camera} 후보 캡처`" /></span><span class="candidate-meta"><strong>{{ cand.camera }}</strong><small>일치율 {{ cand.similarity }}%</small><small>{{ cand.detectedAt }}</small><small>{{ cand.location }}</small></span></button></article>
    <ConfirmModal :open="modalOpen" title="사건 상태를 변경할까요?" message="상태 변경 사유는 감사 로그에 저장됩니다." confirm-text="상태 변경" @close="modalOpen=false" @confirm="changeStatus" />
    <div v-if="selectedCandidate" class="modal-backdrop" @click.self="closeCandidateModal">
      <section class="modal candidate-review-modal">
        <div class="section-heading">
          <div><h2>후보 판정</h2><p>{{ selectedCandidate.caseNumber }} · {{ selectedCandidate.camera }}</p></div>
          <button class="ghost-button" @click="closeCandidateModal">닫기</button>
        </div>
        <div class="review-compare-grid">
          <div>
            <span class="review-label">원본 실종자 사진</span>
            <div class="review-image original"><img src="/mock/missing-person.png" alt="원본 실종자 사진" /></div>
          </div>
          <div>
            <span class="review-label">후보 캡처</span>
            <div class="review-image capture"><img :src="selectedCandidateImage" alt="후보 CCTV 캡처" /></div>
          </div>
        </div>
        <div class="review-detail-grid">
          <span>일치율<strong :class="['similarity-score', similarityTone(selectedCandidate.similarity)]">{{ selectedCandidate.similarity }}%</strong></span>
          <span>CCTV<strong>{{ selectedCandidate.camera }}</strong></span>
          <span>탐지 일시<strong>{{ selectedCandidate.detectedAt }}</strong></span>
          <span>위치<strong>{{ selectedCandidate.location }}</strong></span>
          <span>소스<strong>{{ selectedCandidate.source }}</strong></span>
          <span>구역<strong>{{ selectedCandidate.zone }}</strong></span>
        </div>
        <div class="review-decision-group">
          <button :class="{ active: reviewDecision === 'confirmed' }" @click="reviewDecision = 'confirmed'">대상 확정</button>
          <button :class="{ active: reviewDecision === 'hold' }" @click="reviewDecision = 'hold'">보류</button>
          <button :class="{ active: reviewDecision === 'rejected' }" @click="reviewDecision = 'rejected'">대상 아님</button>
        </div>
        <label class="review-reason">판정 근거<textarea v-model="reviewReason" placeholder="판정 근거와 확인 내용을 입력하세요." /></label>
        <div class="modal-actions">
          <button class="ghost-button" @click="closeCandidateModal">취소</button>
          <button class="primary-button" @click="submitCandidateReview">판정 저장</button>
        </div>
      </section>
    </div>
  </section>
</template>
