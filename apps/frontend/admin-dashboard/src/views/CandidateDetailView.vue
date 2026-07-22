<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { getCandidates, reviewCandidate } from "../api/mockApi";
import ConfirmModal from "../components/common/ConfirmModal.vue";

const route = useRoute();
const router = useRouter();
const item = ref(null);
const decision = ref("confirmed");
const modalOpen = ref(false);

const decisionOptions = [
  { value: "confirmed", label: "대상 확정", desc: "실종자로 판단하고 사건 동선에 반영" },
  { value: "possible", label: "후보", desc: "추가 확인이 필요한 유사 후보로 보류" },
  { value: "rejected", label: "대상 아님", desc: "실종자와 무관한 탐지 결과로 제외" }
];

const label = computed(() => decisionOptions.find((option) => option.value === decision.value)?.label || "후보");

onMounted(async () => {
  item.value = (await getCandidates()).find((x) => x.id === route.params.candidateId);
});

const submit = async () => {
  await reviewCandidate(item.value.id, { decision: decision.value });
  modalOpen.value = false;
  alert("판정이 저장되었습니다.");
  router.push("/admin/candidates");
};
</script>

<template>
  <section v-if="item" class="detail-layout candidate-detail">
    <article class="content-panel candidate-review-panel">
      <div class="candidate-detail-header">
        <div>
          <span class="eyebrow">후보 상세 검토</span>
          <h2>{{ item.caseNumber }}</h2>
        </div>
        <span class="similarity-pill">AI 유사도 {{ item.similarity }}%</span>
      </div>

      <div class="review-compare-grid">
        <div>
          <span class="review-label">원본 실종자 사진</span>
          <div class="review-image">실종자 기준 사진</div>
        </div>
        <div>
          <span class="review-label">후보 캡처</span>
          <div class="review-image capture">{{ item.image }}</div>
        </div>
      </div>

      <div class="video-player">후보 영상 재생 · 탐지 전후 시점 이동</div>
    </article>

    <aside class="candidate-side-stack">
      <article class="content-panel candidate-info-panel">
        <h2>후보 정보</h2>
        <div class="candidate-info-list">
          <span><small>사건 번호</small><strong>{{ item.caseNumber }}</strong></span>
          <span><small>CCTV</small><strong>{{ item.camera }}</strong></span>
          <span class="wide"><small>위치</small><strong>{{ item.location }}</strong></span>
          <span><small>탐지 시각</small><strong>{{ item.detectedAt }}</strong></span>
          <span><small>AI 유사도</small><strong>{{ item.similarity }}%</strong></span>
          <span><small>탐지 방식</small><strong>{{ item.source }}</strong></span>
        </div>
      </article>

      <article class="content-panel admin-decision-panel">
        <div class="decision-heading">
          <h2>관리자 판정</h2>
          <p>최종 판단 결과와 근거를 저장합니다.</p>
        </div>

        <div class="decision-options">
          <button
            v-for="option in decisionOptions"
            :key="option.value"
            type="button"
            :class="{ active: decision === option.value }"
            @click="decision = option.value"
          >
            <strong>{{ option.label }}</strong>
            <span>{{ option.desc }}</span>
          </button>
        </div>

        <label class="review-reason">
          판정 근거
          <textarea placeholder="예: 의상 색상과 보행 방향은 유사하지만 얼굴 식별이 일부 제한됨" />
        </label>

        <div class="decision-checks">
          <label class="check-row"><input type="checkbox" /> 추정 동선에 추가</label>
          <label class="check-row"><input type="checkbox" /> 현장 담당자에게 공유</label>
        </div>

        <div class="form-actions">
          <button class="ghost-button" @click="router.back()">취소</button>
          <button class="primary-button" @click="modalOpen = true">판정 저장</button>
        </div>
      </article>
    </aside>

    <ConfirmModal
      :open="modalOpen"
      title="후보 판정을 저장할까요?"
      :message="`${label} 상태로 저장합니다.`"
      confirm-text="저장"
      @close="modalOpen = false"
      @confirm="submit"
    />
  </section>
</template>
