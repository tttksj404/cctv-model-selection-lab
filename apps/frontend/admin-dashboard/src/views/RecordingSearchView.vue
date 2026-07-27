<script setup>
import { computed, onMounted, ref } from "vue";
import { getCases, getScanJobs } from "../api/mockApi";
import { useRouter } from "vue-router";
import StatusBadge from "../components/common/StatusBadge.vue";

const router = useRouter();
const cases = ref([]);
const jobs = ref([]);
const form = ref({ caseNumber: "", searchArea: "", fromDate: "", fromTime: "", toDate: "", toTime: "" });
const caseDropdownOpen = ref(false);
const cancelTarget = ref(null);
const cancelModalOpen = ref(false);

const selectedCase = computed(() => cases.value.find((item) => item.caseNumber === form.value.caseNumber) || cases.value[0]);

onMounted(async () => {
  cases.value = await getCases();
  jobs.value = await getScanJobs();
});

const selectCase = (caseItem) => {
  form.value.caseNumber = caseItem.caseNumber;
  caseDropdownOpen.value = false;
};

const requestSearch = () => {
  const from = [form.value.fromDate, form.value.fromTime].filter(Boolean).join(" ");
  const to = [form.value.toDate, form.value.toTime].filter(Boolean).join(" ");

  jobs.value.unshift({
    id: `scan-${Date.now()}`,
    caseNumber: form.value.caseNumber || cases.value[0]?.caseNumber,
    camera: form.value.searchArea ? `${form.value.searchArea} 인근 CCTV` : "탐색 지역 인근 CCTV",
    range: `${from || "시작 미지정"}~${to || "종료 미지정"}`,
    status: "searching",
    progress: 3,
    createdAt: "now",
    finishedAt: ""
  });
};

const openCandidateReview = (job) => {
  router.push({ path: "/admin/candidates", query: { caseNumber: job.caseNumber } });
};
const requestCancel = (job) => { cancelTarget.value = job; cancelModalOpen.value = true; };
const cancelJob = () => {
  if (cancelTarget.value) cancelTarget.value.status = "cancelled";
  cancelTarget.value = null;
  cancelModalOpen.value = false;
};
</script>

<template>
  <section class="content-panel">
    <div class="section-heading">
      <div>
        <h2>녹화 영상 탐색</h2>
        <p>탐색 조건 입력, 작업 생성, 진행률 표시를 제공합니다.</p>
      </div>
    </div>

    <div class="recording-search-form">
      <div class="filter-bar recording-filter-main">
        <label class="case-select-field">
          사건
          <div class="case-picker">
            <button type="button" class="case-picker-trigger" @click="caseDropdownOpen = !caseDropdownOpen">
              {{ selectedCase?.caseNumber || "사건 선택" }}
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
          탐색 지역
          <input v-model="form.searchArea" placeholder="예: 강남구 테헤란로 152, 강남역 2번 출구" />
        </label>
      </div>

      <div class="filter-bar recording-filter-time">
        <label>
          시작
          <div class="custom-datetime">
            <input v-model="form.fromDate" type="date" />
            <input v-model="form.fromTime" type="time" />
          </div>
        </label>
        <label>
          종료
          <div class="custom-datetime">
            <input v-model="form.toDate" type="date" />
            <input v-model="form.toTime" type="time" />
          </div>
        </label>
        <button class="search-button" @click="requestSearch">탐색 요청</button>
      </div>
    </div>

    <div class="job-list">
      <article v-for="job in jobs" :key="job.id" class="job-card">
        <div class="job-card-head">
          <strong>{{ job.id }}</strong>
          <StatusBadge :status="job.status" />
        </div>
        <div class="job-meta-grid">
          <span><small>사건 번호</small><strong>{{ job.caseNumber }}</strong></span>
          <span><small>탐색 대상</small><strong>{{ job.camera }}</strong></span>
          <span><small>탐색 시간</small><strong>{{ job.range }}</strong></span>
        </div>
        <div class="progress" :class="`progress-${job.status}`"><span :style="{ width: `${job.progress}%` }" /></div>
        <div class="job-progress-meta">
          <span><strong>{{ job.progress }}%</strong> 완료</span>
          <span>생성 <strong>{{ job.createdAt }}</strong></span>
          <span>완료 <strong>{{ job.finishedAt || "-" }}</strong></span>
        </div>
        <div class="job-card-actions">
          <button v-if="job.status === 'closed'" class="primary-button" @click="openCandidateReview(job)">후보 검토</button>
          <button v-if="job.status === 'failed'" class="reset-button">재시도</button>
          <button v-if="job.status === 'searching'" class="ghost-button" @click="requestCancel(job)">취소</button>
        </div>
      </article>
    </div>
    <div v-if="cancelModalOpen" class="modal-backdrop" @click.self="cancelModalOpen = false">
      <section class="modal">
        <h3>탐색 작업을 취소할까요?</h3>
        <p>진행 중인 녹화영상 탐색 작업이 취소됩니다.</p>
        <textarea placeholder="취소 사유를 적어주세요."></textarea>
        <div class="modal-actions">
          <button class="ghost-button" @click="cancelModalOpen = false">취소</button>
          <button class="primary-button" @click="cancelJob">취소하기</button>
        </div>
      </section>
    </div>
  </section>
</template>
