<script setup>
import { onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { listAuditLogs } from "../api/auditLogApi";
import BasePagination from "../components/common/BasePagination.vue";
import StateBlock from "../components/common/StateBlock.vue";

const PAGE_SIZE = 20;
const ACTION_TYPES = [
  "ADMIN_LOGIN_SUCCESS",
  "ADMIN_LOGIN_FAILURE",
  "ADMIN_LOGIN_RATE_LIMITED",
  "ADMIN_LOGOUT",
  "CASE_INQUIRY_SUCCESS",
  "CASE_INQUIRY_FAILURE",
  "CASE_INQUIRY_RATE_LIMITED",
  "ADMIN_ACCOUNT_CREATE",
  "ADMIN_ACCOUNT_STATUS_CHANGE",
  "ADMIN_PROFILE_UPDATE",
  "ADMIN_PASSWORD_CHANGE",
  "ADMIN_BOOTSTRAP",
  "CASE_CREATED",
  "CASE_UPDATED",
  "CASE_STATUS_CHANGED",
  "CASE_CLOSED",
  "CASE_PHOTO_UPLOADED",
  "CASE_PHOTO_REPLACED",
  "CASE_PHOTO_DELETED",
  "CANDIDATE_REVIEWED",
  "SEARCH_CONDITION_CREATED",
  "SEARCH_CONDITION_UPDATED",
  "SEARCH_CONDITION_DELETED",
  "CASE_CAMERAS_UPDATED",
  "CASE_CAMERA_REMOVED",
  "RECORDING_ANALYSIS_JOB_CREATED",
  "RECORDING_ANALYSIS_JOB_CANCELLED",
  "RECORDING_ANALYSIS_JOB_RETRIED",
  "RECORDING_ANALYSIS_JOB_SUCCEEDED",
  "CAMERA_CREATED",
  "CAMERA_NAME_UPDATED",
  "CAMERA_UPDATED"
];

const logs = ref([]);
const selected = ref(null);
const filters = reactive({
  actionType: "",
  actor: "",
  caseId: "",
  fromDate: "",
  fromTime: "",
  toDate: "",
  toTime: ""
});
const page = ref(1);
const totalPages = ref(1);
const totalCount = ref(0);
const loading = ref(true);
const error = ref("");
let latestRequestId = 0;

const errorMessage = (cause) => cause?.message || "감사 로그를 불러오지 못했습니다.";

const dateTimeToIso = (date, time, end) => {
  if (!date) return undefined;

  const value = new Date(`${date}T${time || "00:00"}:00`);
  if (Number.isNaN(value.getTime())) return undefined;

  if (end) {
    // A date-only end filter is exclusive at the next day's start. When a minute is
    // supplied, include the selected minute while keeping the API's `to` exclusive.
    if (time) value.setMinutes(value.getMinutes() + 1);
    else value.setDate(value.getDate() + 1);
  }
  return value.toISOString();
};

const listParams = () => ({
  actionType: filters.actionType || undefined,
  actor: filters.actor.trim() || undefined,
  caseId: filters.caseId.trim() || undefined,
  from: dateTimeToIso(filters.fromDate, filters.fromTime, false),
  to: dateTimeToIso(filters.toDate, filters.toTime, true),
  page: page.value - 1,
  size: PAGE_SIZE,
  sort: "createdAt,desc"
});

const load = async () => {
  const requestId = ++latestRequestId;
  loading.value = true;
  error.value = "";

  try {
    const result = await listAuditLogs(listParams());
    if (requestId !== latestRequestId) return;
    if (!Array.isArray(result?.data) || !result.meta) {
      throw new Error("감사 로그 응답 형식이 올바르지 않습니다.");
    }
    logs.value = result.data;
    totalPages.value = Math.max(1, Number(result.meta.totalPages) || 0);
    totalCount.value = Number(result.meta.totalElements) || 0;
    if (page.value > totalPages.value) page.value = totalPages.value;
  } catch (cause) {
    if (requestId !== latestRequestId) return;
    logs.value = [];
    totalPages.value = 1;
    totalCount.value = 0;
    error.value = errorMessage(cause);
  } finally {
    if (requestId === latestRequestId) loading.value = false;
  }
};

const resetFilters = () => {
  Object.assign(filters, {
    actionType: "",
    actor: "",
    caseId: "",
    fromDate: "",
    fromTime: "",
    toDate: "",
    toTime: ""
  });
};

const displayActor = (log) => log.adminName || log.adminId || "시스템";
const displayTarget = (log) => {
  if (!log.targetType && !log.targetId) return "-";
  return `${log.targetType || "TARGET"}${log.targetId == null ? "" : ` #${log.targetId}`}`;
};
const formatDate = (value) => {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "medium",
    timeZone: "Asia/Seoul"
  }).format(date);
};
const formatJson = (value) => value == null ? "-" : JSON.stringify(value, null, 2);
const previewJson = (value) => {
  const preview = formatJson(value).replace(/\s+/g, " ");
  return preview.length > 100 ? `${preview.slice(0, 100)}…` : preview;
};

watch(filters, () => {
  if (page.value !== 1) {
    page.value = 1;
    return;
  }
  load();
}, { deep: true });
watch(page, load);
onMounted(load);
onBeforeUnmount(() => {
  latestRequestId += 1;
  selected.value = null;
});
</script>

<template>
  <section class="content-panel">
    <div class="section-heading">
      <div>
        <h2>시스템 로그</h2>
        <p>감사 로그를 서버에서 조회하고 상세 변경 내용을 확인합니다.</p>
      </div>
    </div>

    <div class="filter-bar logs-filter-bar">
      <label>작업 유형
        <select v-model="filters.actionType">
          <option value="">전체</option>
          <option v-for="actionType in ACTION_TYPES" :key="actionType" :value="actionType">
            {{ actionType }}
          </option>
        </select>
      </label>
      <label>사용자<input v-model="filters.actor" autocomplete="off" /></label>
      <label>사건 ID<input v-model="filters.caseId" inputmode="numeric" /></label>
      <label>시작 일시
        <div class="custom-datetime">
          <input v-model="filters.fromDate" type="date" />
          <input v-model="filters.fromTime" type="time" />
        </div>
      </label>
      <label>종료 일시
        <div class="custom-datetime">
          <input v-model="filters.toDate" type="date" />
          <input v-model="filters.toTime" type="time" />
        </div>
      </label>
      <button class="reset-button logs-search-button" type="button" @click="resetFilters">초기화</button>
    </div>

    <StateBlock :loading="loading" :error="error" :empty="logs.length === 0" @retry="load">
      <div class="table-scroll">
        <table class="case-table">
          <thead>
            <tr>
              <th>발생 시각</th>
              <th>사용자</th>
              <th>작업 유형</th>
              <th>대상</th>
              <th>상세</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in logs" :key="log.id">
              <td>{{ formatDate(log.createdAt) }}</td>
              <td>{{ displayActor(log) }}</td>
              <td>{{ log.actionType }}</td>
              <td>{{ displayTarget(log) }}</td>
              <td class="log-detail-cell">
                <span class="log-preview" :title="previewJson(log.detail)">{{ previewJson(log.detail) }}</span>
                <button class="ghost-button" type="button" @click="selected = log">상세보기</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <BasePagination v-model:page="page" :total-pages="totalPages" :total-count="totalCount" />
    </StateBlock>

    <div v-if="selected" class="modal-backdrop" @click.self="selected = null">
      <section class="modal log-detail-modal" role="dialog" aria-modal="true">
        <h3>로그 상세</h3>
        <div class="log-detail-grid">
          <div><span>발생 시각</span><strong>{{ formatDate(selected.createdAt) }}</strong></div>
          <div><span>사용자</span><strong>{{ displayActor(selected) }}</strong></div>
          <div><span>작업 유형</span><strong>{{ selected.actionType }}</strong></div>
          <div><span>대상</span><strong>{{ displayTarget(selected) }}</strong></div>
        </div>
        <div class="log-detail-content"><span>이전 값</span><pre>{{ formatJson(selected.beforeValue) }}</pre></div>
        <div class="log-detail-content"><span>변경 후 값</span><pre>{{ formatJson(selected.afterValue) }}</pre></div>
        <div class="log-detail-content"><span>상세</span><pre>{{ formatJson(selected.detail) }}</pre></div>
        <button class="primary-button" type="button" @click="selected = null">확인</button>
      </section>
    </div>
  </section>
</template>
