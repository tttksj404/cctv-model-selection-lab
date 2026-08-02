<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRouter } from "vue-router";
import StatusBadge from "../components/common/StatusBadge.vue";
import { listCases, listCaseCameras, listSearchConditions } from "../api/caseApi";
import {
  createRecordingAnalysisJob,
  fetchRecordingAnalysisJob,
  listAdminRecordings,
  listRecordingAnalysisJobs,
  cancelRecordingAnalysisJob,
  retryRecordingAnalysisJob
} from "../api/recordingApi";

const router = useRouter();
const cases = ref([]);
const conditions = ref([]);
const caseCameraIds = ref([]);
const recordings = ref([]);
const jobs = ref([]);
const loading = ref(true);
const submitting = ref(false);
const error = ref("");
const caseDropdownOpen = ref(false);
const getMidnight = () => {
  const now = new Date();
  const date = new Date(now.getTime() - now.getTimezoneOffset() * 60000);
  return `${date.toISOString().slice(0, 10)}T00:00`;
};
const form = ref({
  caseId: "",
  conditionId: "",
  recordingId: "",
  searchArea: "",
  fromAt: getMidnight(),
  toAt: getMidnight()
});

const selectedCase = computed(() => cases.value.find((item) => String(item.id) === String(form.value.caseId)));
const selectedCondition = computed(() => conditions.value.find((item) => String(item.id) === String(form.value.conditionId)));
const selectedRecording = computed(() => recordings.value.find((item) => String(item.id) === String(form.value.recordingId)));
const visibleJobs = computed(() => form.value.caseId
  ? jobs.value.filter((job) => String(job.caseId) === String(form.value.caseId))
  : jobs.value);

const toIso = (value) => value ? new Date(value).toISOString() : undefined;
const formatDate = (value) => value ? new Date(value).toLocaleString("ko-KR") : "-";
const recordingLabel = (recording) => {
  const camera = recording.camera?.cameraCode || recording.camera?.cameraName || "카메라";
  return `${camera} · ${formatDate(recording.startTime)} ~ ${formatDate(recording.endTime)}`;
};
const jobProgress = (status) => ({ QUEUED: 3, RUNNING: 50, SUCCEEDED: 100, FAILED: 100, CANCELLED: 100 }[status] ?? 0);
const jobStatus = (status) => ({ QUEUED: "searching", RUNNING: "searching", SUCCEEDED: "closed", FAILED: "failed", CANCELLED: "cancelled" }[status] || "searching");

const loadRecordings = async () => {
  if (!form.value.caseId || caseCameraIds.value.length === 0) {
    recordings.value = [];
    form.value.recordingId = "";
    return;
  }

  const results = await Promise.all(caseCameraIds.value.map((cameraId) => listAdminRecordings({
    cameraId,
    startFrom: toIso(form.value.fromAt),
    startTo: toIso(form.value.toAt),
    page: 0,
    size: 100,
    sort: "startTime,desc"
  })));
  const byId = new Map(results.flatMap((result) => result.data || []).map((recording) => [recording.id, recording]));
  recordings.value = [...byId.values()].sort((left, right) => (
    new Date(right.startTime).getTime() - new Date(left.startTime).getTime()
  ));
  if (!recordings.value.some((item) => String(item.id) === String(form.value.recordingId))) {
    form.value.recordingId = recordings.value[0]?.id ? String(recordings.value[0].id) : "";
  }
};

const loadJobs = async () => {
  if (cases.value.length === 0) {
    jobs.value = [];
    return;
  }
  const results = await Promise.all(cases.value.map((item) => listRecordingAnalysisJobs(item.id)));
  jobs.value = results.flat().sort((left, right) => (
    new Date(right.requestedAt).getTime() - new Date(left.requestedAt).getTime()
  ));
};

const loadCaseData = async () => {
  if (!form.value.caseId) {
    conditions.value = [];
    caseCameraIds.value = [];
    form.value.conditionId = "";
    return;
  }
  const [nextConditions, nextCameras] = await Promise.all([
    listSearchConditions(form.value.caseId),
    listCaseCameras(form.value.caseId)
  ]);
  conditions.value = nextConditions;
  caseCameraIds.value = nextCameras
    .filter((camera) => camera.searchEnabled && !camera.removedAt)
    .map((camera) => camera.cameraId);
  if (!conditions.value.some((item) => String(item.id) === String(form.value.conditionId))) {
    form.value.conditionId = conditions.value[0]?.id ? String(conditions.value[0].id) : "";
  }
};

const load = async () => {
  loading.value = true;
  error.value = "";
  try {
    const result = await listCases({ page: 0, size: 100, sort: "reportedAt,desc" });
    cases.value = (result.data || []).map((item) => ({
      ...item,
      name: item.missingName || item.name || "이름 미등록"
    }));
    await loadJobs();
    await loadCaseData();
    await loadRecordings();
  } catch (exception) {
    error.value = exception.message || "녹화 탐색 정보를 불러오지 못했습니다.";
  } finally {
    loading.value = false;
  }
};

const selectCase = async (caseItem) => {
  form.value.caseId = String(caseItem.id);
  caseDropdownOpen.value = false;
  await loadCaseData();
  await loadRecordings();
};

const selectAllCases = () => {
  form.value.caseId = "";
  form.value.conditionId = "";
  conditions.value = [];
  caseCameraIds.value = [];
  recordings.value = [];
  form.value.recordingId = "";
  caseDropdownOpen.value = false;
};

const requestSearch = async () => {
  const selectedCameraId = selectedRecording.value?.camera?.cameraId;
  if (!form.value.caseId || !form.value.conditionId || !form.value.recordingId
      || !selectedRecording.value || !caseCameraIds.value.includes(selectedCameraId)) {
    error.value = "사건, 탐색 조건, 녹화를 모두 선택해주세요.";
    return;
  }
  submitting.value = true;
  error.value = "";
  try {
    const job = await createRecordingAnalysisJob(form.value.caseId, {
      conditionId: Number(form.value.conditionId),
      recordingId: Number(form.value.recordingId)
    });
    jobs.value.unshift(job);
  } catch (exception) {
    error.value = exception.message || "녹화 분석 작업을 등록하지 못했습니다.";
  } finally {
    submitting.value = false;
  }
};

const refreshJobs = async () => {
  const activeJobs = jobs.value.filter((job) => ["QUEUED", "RUNNING"].includes(job.status));
  await Promise.all(activeJobs.map(async (job) => {
    try {
      const updated = await fetchRecordingAnalysisJob(job.caseId, job.jobId);
      Object.assign(job, updated);
    } catch {
      // Keep the last known state while the next refresh retries the job.
    }
  }));
};

const cancelJob = async (job) => {
  error.value = "";
  try {
    Object.assign(job, await cancelRecordingAnalysisJob(job.caseId, job.jobId));
  } catch (exception) {
    error.value = exception.message || "녹화 분석 작업을 취소하지 못했습니다.";
  }
};

const retryJob = async (job) => {
  error.value = "";
  try {
    Object.assign(job, await retryRecordingAnalysisJob(job.caseId, job.jobId));
  } catch (exception) {
    error.value = exception.message || "녹화 분석 작업을 재시도하지 못했습니다.";
  }
};

const openCandidateReview = (job) => {
  router.push({ path: "/admin/candidates", query: { caseId: job.caseId } });
};

let jobRefreshTimer;
onMounted(async () => {
  await load();
  jobRefreshTimer = window.setInterval(refreshJobs, 3000);
});
onUnmounted(() => {
  if (jobRefreshTimer) window.clearInterval(jobRefreshTimer);
});
</script>

<template>
  <section class="content-panel">
    <div class="section-heading">
      <div><h2>녹화 영상 탐색</h2><p>사건의 탐색 조건과 저장된 녹화를 선택해 분석 작업을 등록합니다.</p></div>
    </div>

    <p v-if="loading" class="empty-state">녹화 탐색 정보를 불러오는 중입니다.</p>
    <p v-else-if="error" class="error-message">{{ error }}</p>

    <div v-else class="recording-search-form">
      <div class="filter-bar recording-filter-main">
        <label class="case-select-field">사건
          <div class="case-picker">
            <button type="button" class="case-picker-trigger" @click="caseDropdownOpen = !caseDropdownOpen">{{ selectedCase?.caseNumber || "사건 선택" }}</button>
            <div v-if="caseDropdownOpen" class="case-picker-menu">
              <button type="button" class="case-picker-option" @click="selectAllCases">사건 선택</button>
              <button v-for="item in cases" :key="item.id" type="button" class="case-picker-option" @click="selectCase(item)">{{ item.caseNumber }} · {{ item.name }}</button>
            </div>
          </div>
        </label>
        <label>탐색 조건
          <select v-model="form.conditionId">
            <option value="">조건 선택</option>
            <option v-for="condition in conditions" :key="condition.id" :value="String(condition.id)">{{ condition.prompt || `조건 ${condition.id}` }}</option>
          </select>
        </label>
        <label>탐색 지역
          <input :value="selectedCondition?.searchArea || ''" placeholder="탐색 조건에 저장된 지역" readonly />
        </label>
      </div>
      <div class="filter-bar recording-filter-time">
        <label>시작<input v-model="form.fromAt" type="datetime-local" @change="loadRecordings" /></label>
        <label>종료<input v-model="form.toAt" type="datetime-local" @change="loadRecordings" /></label>
        <label>녹화
          <select v-model="form.recordingId">
            <option value="">녹화 선택</option>
            <option v-for="recording in recordings" :key="recording.id" :value="String(recording.id)">{{ recordingLabel(recording) }}</option>
          </select>
        </label>
        <button class="search-button" :disabled="submitting" @click="requestSearch">{{ submitting ? "등록 중..." : "탐색 요청" }}</button>
      </div>
      <p v-if="selectedRecording" class="muted-text">선택된 녹화: {{ recordingLabel(selectedRecording) }}</p>
    </div>

    <div v-if="!loading" class="job-list">
      <p v-if="visibleJobs.length === 0" class="empty-state">등록된 녹화 분석 작업이 없습니다.</p>
      <article v-for="job in visibleJobs" :key="job.jobId" class="job-card">
        <div class="job-card-head"><strong>JOB-{{ job.jobId }}</strong><StatusBadge :status="jobStatus(job.status)" /></div>
        <div class="job-meta-grid">
          <span><small>사건 번호</small><strong>{{ cases.find((item) => String(item.id) === String(job.caseId))?.caseNumber || job.caseId }}</strong></span>
          <span><small>녹화 ID</small><strong>{{ job.recordingId }}</strong></span>
          <span><small>요청 시각</small><strong>{{ formatDate(job.requestedAt) }}</strong></span>
        </div>
        <div class="progress" :class="`progress-${jobStatus(job.status)}`"><span :style="{ width: `${jobProgress(job.status)}%` }" /></div>
        <div class="job-progress-meta"><span><strong>{{ jobProgress(job.status) }}%</strong> 완료</span><span>상태 <strong>{{ job.status }}</strong></span></div>
        <div class="job-card-actions"><button v-if="job.status === 'SUCCEEDED'" class="primary-button" @click="openCandidateReview(job)">후보 검토</button><button v-if="['QUEUED', 'RUNNING'].includes(job.status)" class="ghost-button" @click="cancelJob(job)">취소</button><button v-if="job.status === 'FAILED'" class="reset-button" @click="retryJob(job)">재시도</button></div>
      </article>
    </div>
  </section>
</template>
