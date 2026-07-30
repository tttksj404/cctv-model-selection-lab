<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { closeCase, getCase, updateCaseStatus } from "../api/caseApi";
import ConfirmModal from "../components/common/ConfirmModal.vue";
import { mapCaseDetail, toBackendStatus } from "../domain/caseMapper";

const route = useRoute();
const router = useRouter();

const STATUS_STEPS = Object.freeze([
  { value: "received", label: "접수" },
  { value: "searching", label: "탐색 중" },
  { value: "candidate_found", label: "후보 발견" },
  { value: "field_search", label: "현장 탐색" },
  { value: "closed", label: "종료" }
]);

const ALLOWED_TRANSITIONS = Object.freeze({
  received: ["searching"],
  searching: ["candidate_found"],
  candidate_found: ["searching", "field_search"],
  field_search: ["searching"],
  closed: []
});

const rawCase = ref(null);
const item = ref(null);
const loading = ref(true);
const loadError = ref("");
const notFound = ref(false);
const actionMessage = ref("");

// Candidate and route APIs are not implemented yet. Keep the real empty state instead of mock data.
const candidates = ref([]);
const routePoints = ref([]);

const nextStatus = ref("");
const statusModalOpen = ref(false);
const statusReason = ref("");
const statusReasonError = ref("");
const statusLoading = ref(false);

const closeModalOpen = ref(false);
const closeReason = ref("");
const closeReasonError = ref("");
const closeLoading = ref(false);
const forceCloseRequired = ref(false);
let loadRequestId = 0;
let actionRequestId = 0;

const statusLabels = Object.freeze(Object.fromEntries(STATUS_STEPS.map((step) => [step.value, step.label])));
const statusOptions = computed(() => (
  ALLOWED_TRANSITIONS[item.value?.status] ?? []
).map((value) => ({ value, label: statusLabels[value] ?? value })));
const isClosed = computed(() => item.value?.status === "closed");
const statusConfirmDisabled = computed(() => !statusReason.value.trim() || !nextStatus.value);
const closeConfirmDisabled = computed(() => !closeReason.value.trim());
const closeModalTitle = computed(() => forceCloseRequired.value
  ? "사건을 강제로 종료할까요?"
  : "사건을 종료할까요?");
const closeModalMessage = computed(() => forceCloseRequired.value
  ? "미처리 후보 또는 실행 중인 작업이 있습니다. 강제 종료하면 실행 중인 작업이 취소됩니다."
  : "먼저 일반 종료를 시도합니다. 처리 중인 작업이 있으면 강제 종료 여부를 다시 확인합니다.");
const closeConfirmText = computed(() => forceCloseRequired.value ? "강제 종료" : "사건 종료");
const personSummary = computed(() => {
  if (!item.value) return "—";
  const parts = [item.value.gender || null, item.value.age ? `${item.value.age}세` : null].filter(Boolean);
  return parts.length ? parts.join(" · ") : "—";
});

function syncNextStatus() {
  nextStatus.value = ALLOWED_TRANSITIONS[item.value?.status]?.[0] ?? "";
}

function applyRawCase(source) {
  rawCase.value = source;
  item.value = mapCaseDetail(source);
  syncNextStatus();
}

function applyStateResponse(state) {
  applyRawCase({ ...rawCase.value, ...state });
}

function readableError(error, fallback) {
  return error?.message || fallback;
}

async function loadCase({ showLoading = true } = {}) {
  const requestId = ++loadRequestId;
  const caseId = String(route.params.caseId);
  if (showLoading) loading.value = true;
  loadError.value = "";
  notFound.value = false;

  try {
    const source = await getCase(caseId);
    if (requestId !== loadRequestId || String(route.params.caseId) !== caseId) return false;
    applyRawCase(source);
    return true;
  } catch (error) {
    if (requestId !== loadRequestId || String(route.params.caseId) !== caseId) return false;
    item.value = null;
    rawCase.value = null;
    if (error?.status === 404) {
      notFound.value = true;
    } else {
      loadError.value = readableError(error, "사건 정보를 불러오지 못했습니다.");
    }
    return false;
  } finally {
    if (showLoading && requestId === loadRequestId && String(route.params.caseId) === caseId) {
      loading.value = false;
    }
  }
}

function openStatusModal() {
  if (!nextStatus.value || isClosed.value) return;
  statusReason.value = "";
  statusReasonError.value = "";
  actionMessage.value = "";
  statusModalOpen.value = true;
}

function closeStatusModal() {
  if (statusLoading.value) return;
  statusModalOpen.value = false;
  statusReasonError.value = "";
}

async function refetchAfterConflict(message, actionId, caseId) {
  if (
    await loadCase({ showLoading: false })
      && actionId === actionRequestId
      && String(item.value?.id) === caseId
  ) {
    actionMessage.value = message;
  }
}

async function changeStatus() {
  const reason = statusReason.value.trim();
  if (!reason) {
    statusReasonError.value = "상태 변경 사유를 입력해 주세요.";
    return;
  }

  const actionId = ++actionRequestId;
  const caseId = String(item.value.id);
  statusLoading.value = true;
  statusReasonError.value = "";
  try {
    const previousStatus = item.value.status;
    const targetStatus = nextStatus.value;
    const state = await updateCaseStatus(caseId, {
      status: toBackendStatus(targetStatus),
      reason
    });
    if (actionId !== actionRequestId || String(item.value?.id) !== caseId) return;
    applyStateResponse(state);
    statusModalOpen.value = false;
    actionMessage.value = `${statusLabels[previousStatus]}에서 ${statusLabels[targetStatus]} 상태로 변경했습니다.`;
  } catch (error) {
    if (actionId !== actionRequestId || String(item.value?.id) !== caseId) return;
    if (error?.status === 409) {
      statusModalOpen.value = false;
      await refetchAfterConflict(
        "다른 요청으로 사건 상태가 변경되어 최신 정보를 다시 불러왔습니다.",
        actionId,
        caseId
      );
    } else if (
      error?.status === 422
        && item.value?.status === "received"
        && nextStatus.value === "searching"
    ) {
      statusReasonError.value = readableError(
        error,
        "탐색을 시작하려면 탐색 조건과 활성 카메라가 필요합니다."
      );
    } else {
      statusReasonError.value = readableError(error, "사건 상태를 변경하지 못했습니다.");
    }
  } finally {
    if (actionId === actionRequestId) statusLoading.value = false;
  }
}

function openCloseModal() {
  if (isClosed.value) return;
  closeReason.value = "";
  closeReasonError.value = "";
  forceCloseRequired.value = false;
  actionMessage.value = "";
  closeModalOpen.value = true;
}

function dismissCloseModal() {
  if (closeLoading.value) return;
  closeModalOpen.value = false;
  closeReasonError.value = "";
  forceCloseRequired.value = false;
}

async function submitClose() {
  const reason = closeReason.value.trim();
  if (!reason) {
    closeReasonError.value = "종료 사유를 입력해 주세요.";
    return;
  }

  const actionId = ++actionRequestId;
  const caseId = String(item.value.id);
  closeLoading.value = true;
  closeReasonError.value = "";
  try {
    const state = await closeCase(caseId, {
      reason,
      force: forceCloseRequired.value
    });
    if (actionId !== actionRequestId || String(item.value?.id) !== caseId) return;
    applyStateResponse(state);
    closeModalOpen.value = false;
    forceCloseRequired.value = false;
    actionMessage.value = "사건을 종료했습니다.";
  } catch (error) {
    if (actionId !== actionRequestId || String(item.value?.id) !== caseId) return;
    if (error?.status === 409 && error?.code === "CASE_CLOSE_CONFLICT") {
      const refreshed = await loadCase({ showLoading: false });
      if (actionId !== actionRequestId || String(item.value?.id) !== caseId) return;
      if (!refreshed) {
        closeModalOpen.value = false;
        return;
      }
      if (item.value?.status === "closed") {
        closeModalOpen.value = false;
        actionMessage.value = "사건이 이미 종료되어 최신 정보를 불러왔습니다.";
      } else {
        forceCloseRequired.value = true;
        closeReasonError.value = "미처리 후보 또는 실행 중인 작업이 있습니다. 계속하려면 강제 종료를 다시 확인해 주세요.";
      }
    } else if (error?.status === 409) {
      closeModalOpen.value = false;
      await refetchAfterConflict(
        "다른 요청으로 사건 상태가 변경되어 최신 정보를 다시 불러왔습니다.",
        actionId,
        caseId
      );
    } else {
      closeReasonError.value = readableError(error, "사건을 종료하지 못했습니다.");
    }
  } finally {
    if (actionId === actionRequestId) closeLoading.value = false;
  }
}

watch(statusReason, () => {
  if (statusReasonError.value === "상태 변경 사유를 입력해 주세요.") statusReasonError.value = "";
});
watch(closeReason, () => {
  if (closeReasonError.value === "종료 사유를 입력해 주세요.") closeReasonError.value = "";
});
watch(() => route.params.caseId, () => {
  actionRequestId += 1;
  statusModalOpen.value = false;
  closeModalOpen.value = false;
  statusLoading.value = false;
  closeLoading.value = false;
  forceCloseRequired.value = false;
  actionMessage.value = "";
  loadCase();
});

onMounted(() => loadCase());
onBeforeUnmount(() => {
  loadRequestId += 1;
  actionRequestId += 1;
});
</script>

<template>
  <section v-if="loading" class="content-panel">
    <div class="state-view" role="status"><strong>사건 정보를 불러오는 중입니다.</strong></div>
  </section>

  <section v-else-if="notFound" class="content-panel">
    <div class="state-view error">
      <strong>사건을 찾을 수 없습니다.</strong>
      <p>삭제되었거나 존재하지 않는 사건 번호입니다.</p>
      <button type="button" @click="router.push('/admin/cases')">사건 목록으로</button>
    </div>
  </section>

  <section v-else-if="loadError" class="content-panel">
    <div class="state-view error">
      <strong>{{ loadError }}</strong>
      <button type="button" @click="loadCase()">다시 시도</button>
    </div>
  </section>

  <section v-else-if="item" class="detail-layout">
    <div class="case-detail-main">
      <article class="content-panel">
        <div class="section-heading case-detail-heading">
          <div>
            <p class="mono">{{ item.caseNumber }}</p>
            <h2>{{ item.name || "이름 미상" }}</h2>
          </div>
          <div class="status-flow case-status-steps" aria-label="현재 사건 상태">
            <span
              v-for="step in STATUS_STEPS"
              :key="step.value"
              :class="{ active: item.status === step.value }"
            >{{ step.label }}</span>
          </div>
        </div>

        <p v-if="actionMessage" class="case-action-message" role="status">{{ actionMessage }}</p>

        <div class="profile-block">
          <div class="portrait">
            <img v-if="item.photoUrl" :src="item.photoUrl" :alt="`${item.name || '실종자'} 기준 사진`" />
            <span v-else>등록된 사진이 없습니다.</span>
          </div>
          <div class="info-grid">
            <span>성별/나이<strong>{{ personSummary }}</strong></span>
            <span>신고자<strong>{{ item.reporter || "—" }}</strong></span>
            <span>신고 시간<strong>{{ item.reportedAt || "—" }}</strong></span>
            <span>마지막 목격<strong>{{ item.lastSeenAt || "—" }}</strong></span>
            <span>목격 위치<strong>{{ item.lastSeenLocation || "—" }}</strong></span>
            <span>담당자<strong>{{ item.assignee && item.assignee !== "-" ? item.assignee : "미배정" }}</strong></span>
            <span class="info-wide">인상착의<strong>{{ item.appearance || "—" }}</strong></span>
            <span class="info-wide">실종 경위<strong>{{ item.reportContent || "—" }}</strong></span>
            <span v-if="item.closedAt" class="info-wide">종료 일시<strong>{{ item.closedAt }}</strong></span>
            <span class="profile-action">
              <button
                type="button"
                class="ghost-button"
                @click="router.push(`/admin/cases/${item.id}/edit`)"
              >{{ isClosed ? "사진 관리" : "사건 정보 수정" }}</button>
            </span>
          </div>
        </div>

        <div class="section-heading status-change-heading">
          <div>
            <h2>상태 관리</h2>
            <p v-if="isClosed">종료된 사건은 더 이상 상태를 변경할 수 없습니다.</p>
            <p v-else-if="statusOptions.length">백엔드에서 허용하는 다음 상태만 선택할 수 있습니다.</p>
            <p v-else>현재 상태에서 가능한 일반 상태 전이가 없습니다.</p>
          </div>
          <div v-if="!isClosed" class="status-actions">
            <select v-if="statusOptions.length" v-model="nextStatus" aria-label="변경할 사건 상태">
              <option v-for="option in statusOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
            <button
              v-if="statusOptions.length"
              type="button"
              class="primary-button"
              @click="openStatusModal"
            >상태 변경</button>
            <button type="button" class="danger-button" @click="openCloseModal">사건 종료</button>
          </div>
        </div>
      </article>

      <article class="content-panel">
        <h2>추정 동선</h2>
        <div v-if="routePoints.length === 0" class="state-view">
          <strong>확인된 동선이 없습니다.</strong>
          <p>후보가 확정되고 동선 데이터가 생성되면 여기에 표시됩니다.</p>
        </div>
      </article>
    </div>

    <article class="content-panel">
      <h2>후보 탐지 목록</h2>
      <div v-if="candidates.length === 0" class="state-view">
        <strong>탐지된 후보가 없습니다.</strong>
        <p>탐색 중 발견된 후보가 여기에 표시됩니다.</p>
      </div>
    </article>

    <ConfirmModal
      v-model:reason="statusReason"
      :open="statusModalOpen"
      title="사건 상태를 변경할까요?"
      :message="`${statusLabels[item.status]}에서 ${statusLabels[nextStatus]} 상태로 변경합니다.`"
      confirm-text="상태 변경"
      show-reason
      :reason-error="statusReasonError"
      :loading="statusLoading"
      :confirm-disabled="statusConfirmDisabled"
      @close="closeStatusModal"
      @confirm="changeStatus"
    />

    <ConfirmModal
      v-model:reason="closeReason"
      :open="closeModalOpen"
      :title="closeModalTitle"
      :message="closeModalMessage"
      :confirm-text="closeConfirmText"
      show-reason
      :reason-error="closeReasonError"
      :loading="closeLoading"
      :confirm-disabled="closeConfirmDisabled"
      @close="dismissCloseModal"
      @confirm="submitClose"
    />
  </section>
</template>

<style scoped>
.case-action-message {
  margin: 0 0 18px;
  border: 1px solid #a9cfdd;
  border-radius: 7px;
  padding: 10px 12px;
  background: #eef8fb;
  color: #235f7c;
  font-size: 13px;
  font-weight: 700;
}

.portrait span {
  padding: 18px;
  color: #64748b;
}

.status-change-heading {
  margin-top: 24px;
  border-top: 1px solid #e4e8ef;
  padding-top: 20px;
}

.status-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.danger-button {
  min-height: 38px;
  border: 1px solid #d88982;
  border-radius: 7px;
  padding: 0 14px;
  background: #fff0ee;
  color: #9b382f;
  font-weight: 700;
}
</style>
