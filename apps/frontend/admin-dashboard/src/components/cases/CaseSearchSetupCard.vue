<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from "vue";
import {
  addCaseCameras,
  createSearchCondition,
  deleteSearchCondition,
  listCaseCameras,
  listSearchConditions,
  removeCaseCamera,
  replaceSearchCondition
} from "../../api/caseApi";
import { listCameras } from "../../api/cameraApi";
import { mapCamera } from "../../domain/cameraMapper";
import { formatKstDateTime } from "../../domain/caseMapper";
import {
  buildCanonicalPrompt,
  buildSearchConditionPayload,
  COLOR_OPTIONS,
  emptyDescriptor,
  GENDER_OPTIONS,
  parseCanonicalPrompt,
  SLEEVE_OPTIONS,
  toLocalDateTimeInput,
  validateSearchConditionForm
} from "../../domain/searchCondition";
import BasePagination from "../common/BasePagination.vue";
import StateBlock from "../common/StateBlock.vue";
import StatusBadge from "../common/StatusBadge.vue";

const props = defineProps({
  caseId: { type: [String, Number], required: true },
  closed: Boolean,
  conditions: { type: Array, default: () => [] },
  cameras: { type: Array, default: () => [] },
  loading: Boolean,
  error: { type: String, default: "" }
});

const emit = defineEmits(["readiness-change", "case-refresh-requested"]);

const conditionsSection = ref(null);
const camerasSection = ref(null);
const localConditions = ref([]);
const localCameras = ref([]);
const localLoading = ref(false);
const localError = ref("");
const operationError = ref("");
const successMessage = ref("");
const mutationKind = ref("");
const pickerMutationError = ref("");
let setupRequestId = 0;
let mutationRequestId = 0;
const mutationBusy = computed(() => Boolean(mutationKind.value));

const usableConditionCount = computed(() => (
  localConditions.value.filter((condition) => condition.realtimeUsable === true).length
));
const activeCameras = computed(() => (
  localCameras.value.filter((camera) => camera.searchEnabled === true)
));
const activeCameraCount = computed(() => activeCameras.value.length);
const ready = computed(() => (
  !localLoading.value
    && !localError.value
    && usableConditionCount.value > 0
    && activeCameraCount.value > 0
));

watch(
  () => [props.caseId, props.conditions, props.cameras, props.loading, props.error],
  ([caseId, conditions, cameras, loading, error], previous) => {
    if (previous && String(previous[0]) !== String(caseId)) {
      setupRequestId += 1;
      mutationRequestId += 1;
      mutationKind.value = "";
      closeConditionForm();
      closeCameraPicker();
      operationError.value = "";
      successMessage.value = "";
    }
    localConditions.value = Array.isArray(conditions) ? [...conditions] : [];
    localCameras.value = Array.isArray(cameras) ? [...cameras] : [];
    localLoading.value = Boolean(loading);
    localError.value = error || "";
  },
  { immediate: true }
);

watch(
  () => [usableConditionCount.value, activeCameraCount.value, ready.value, localLoading.value, localError.value],
  () => emit("readiness-change", {
    usableConditionCount: usableConditionCount.value,
    activeCameraCount: activeCameraCount.value,
    ready: ready.value,
    loading: localLoading.value,
    error: localError.value
  }),
  { immediate: true }
);

watch(() => props.closed, (closed) => {
  if (!closed) return;
  mutationRequestId += 1;
  mutationKind.value = "";
  closeConditionForm();
  closeCameraPicker();
});

function readableError(error, fallback) {
  return error?.message || fallback;
}

async function reload() {
  const requestId = ++setupRequestId;
  const caseId = String(props.caseId);
  localLoading.value = true;
  localError.value = "";

  const [conditionsResult, camerasResult] = await Promise.allSettled([
    listSearchConditions(caseId),
    listCaseCameras(caseId)
  ]);
  if (requestId !== setupRequestId || String(props.caseId) !== caseId) return false;

  const errors = [];
  if (conditionsResult.status === "fulfilled") {
    localConditions.value = conditionsResult.value || [];
  } else {
    errors.push(readableError(conditionsResult.reason, "탐색 조건을 불러오지 못했습니다."));
  }
  if (camerasResult.status === "fulfilled") {
    localCameras.value = camerasResult.value || [];
  } else {
    errors.push(readableError(camerasResult.reason, "배정 카메라를 불러오지 못했습니다."));
  }
  localError.value = [...new Set(errors)].join(" ");
  localLoading.value = false;
  return errors.length === 0;
}

function scrollTo(element) {
  element?.scrollIntoView?.({ behavior: "smooth", block: "center" });
  element?.focus?.({ preventScroll: true });
}

function focusConditions() {
  scrollTo(conditionsSection.value);
}

function focusCameras() {
  scrollTo(camerasSection.value);
}

function focusMissing() {
  if (usableConditionCount.value === 0) focusConditions();
  else if (activeCameraCount.value === 0) focusCameras();
}

defineExpose({ reload, focusConditions, focusCameras, focusMissing });

const formOpen = ref(false);
const editingConditionId = ref(null);
const legacyEditWarning = ref(false);
const formError = ref("");
const conditionForm = reactive({
  subject: emptyDescriptor(),
  exclusionEnabled: false,
  exclusion: emptyDescriptor(),
  searchStart: "",
  searchEnd: "",
  searchArea: ""
});
const canonicalPreview = computed(() => buildCanonicalPrompt(conditionForm.subject));
const exclusionPreview = computed(() => (
  conditionForm.exclusionEnabled ? buildCanonicalPrompt(conditionForm.exclusion) : ""
));

function resetConditionForm() {
  conditionForm.subject = emptyDescriptor();
  conditionForm.exclusionEnabled = false;
  conditionForm.exclusion = emptyDescriptor();
  conditionForm.searchStart = "";
  conditionForm.searchEnd = "";
  conditionForm.searchArea = "";
  formError.value = "";
  legacyEditWarning.value = false;
}

function openCreateCondition() {
  if (props.closed || mutationKind.value) return;
  resetConditionForm();
  editingConditionId.value = null;
  formOpen.value = true;
  operationError.value = "";
  successMessage.value = "";
}

function openEditCondition(condition) {
  if (props.closed || mutationKind.value) return;
  resetConditionForm();
  editingConditionId.value = condition.id;
  conditionForm.subject = parseCanonicalPrompt(condition.normalizedPrompt) || emptyDescriptor();
  const parsedExclusion = parseCanonicalPrompt(condition.normalizedExclusionPrompt);
  conditionForm.exclusionEnabled = Boolean(condition.exclusionPrompt || condition.normalizedExclusionPrompt);
  conditionForm.exclusion = parsedExclusion || emptyDescriptor();
  conditionForm.searchStart = toLocalDateTimeInput(condition.searchStart);
  conditionForm.searchEnd = toLocalDateTimeInput(condition.searchEnd);
  conditionForm.searchArea = condition.searchArea || "";
  legacyEditWarning.value = condition.realtimeUsable !== true
    || !parseCanonicalPrompt(condition.normalizedPrompt)
    || (conditionForm.exclusionEnabled && !parsedExclusion);
  formOpen.value = true;
  operationError.value = "";
  successMessage.value = "";
}

function closeConditionForm() {
  if (mutationKind.value === "condition") return;
  formOpen.value = false;
  editingConditionId.value = null;
  resetConditionForm();
}

async function handleMutationFailure(error, fallback, actionId, caseId, surface = "card") {
  if (actionId !== mutationRequestId || String(props.caseId) !== caseId) return;
  if ([409, 422].includes(error?.status)) {
    emit("case-refresh-requested");
    await reload();
  }
  if (actionId !== mutationRequestId || String(props.caseId) !== caseId) return;
  const message = readableError(error, fallback);
  if (surface === "picker") pickerMutationError.value = message;
  else operationError.value = message;
}

async function saveCondition() {
  if (props.closed || mutationKind.value) return;
  formError.value = validateSearchConditionForm(conditionForm);
  if (formError.value) return;

  const actionId = ++mutationRequestId;
  const caseId = String(props.caseId);
  mutationKind.value = "condition";
  operationError.value = "";
  successMessage.value = "";
  try {
    const payload = buildSearchConditionPayload(conditionForm);
    if (editingConditionId.value === null) {
      await createSearchCondition(caseId, payload);
    } else {
      await replaceSearchCondition(caseId, editingConditionId.value, payload);
    }
    if (actionId !== mutationRequestId || String(props.caseId) !== caseId) return;
    const wasEditing = editingConditionId.value !== null;
    mutationKind.value = "";
    formOpen.value = false;
    editingConditionId.value = null;
    resetConditionForm();
    await reload();
    if (actionId !== mutationRequestId || String(props.caseId) !== caseId) return;
    successMessage.value = wasEditing ? "탐색 조건을 수정했습니다." : "탐색 조건을 추가했습니다.";
  } catch (error) {
    await handleMutationFailure(error, "탐색 조건을 저장하지 못했습니다.", actionId, caseId);
  } finally {
    if (actionId === mutationRequestId) mutationKind.value = "";
  }
}

async function deleteCondition(condition) {
  if (props.closed || mutationKind.value) return;
  if (!globalThis.confirm?.("이 탐색 조건을 삭제할까요?")) return;
  const actionId = ++mutationRequestId;
  const caseId = String(props.caseId);
  mutationKind.value = "condition";
  operationError.value = "";
  successMessage.value = "";
  try {
    await deleteSearchCondition(caseId, condition.id);
    if (actionId !== mutationRequestId || String(props.caseId) !== caseId) return;
    mutationKind.value = "";
    await reload();
    if (actionId === mutationRequestId && String(props.caseId) === caseId) {
      successMessage.value = "탐색 조건을 삭제했습니다.";
    }
  } catch (error) {
    await handleMutationFailure(error, "탐색 조건을 삭제하지 못했습니다.", actionId, caseId);
  } finally {
    if (actionId === mutationRequestId) mutationKind.value = "";
  }
}

const pickerOpen = ref(false);
const pickerSearchInput = ref("");
const pickerQuery = ref("");
const pickerRows = ref([]);
const pickerPage = ref(1);
const pickerTotalPages = ref(1);
const pickerTotalCount = ref(0);
const pickerLoading = ref(false);
const pickerError = ref("");
const selectedCameraIds = ref([]);
const selectedWarningCameraIds = ref([]);
let pickerRequestId = 0;

const activeCameraIds = computed(() => new Set(activeCameras.value.map(({ cameraId }) => cameraId)));
const selectedWarningCount = computed(() => selectedWarningCameraIds.value.length);

async function loadPicker() {
  const requestId = ++pickerRequestId;
  const caseId = String(props.caseId);
  pickerLoading.value = true;
  pickerError.value = "";
  try {
    const result = await listCameras({
      search: pickerQuery.value.trim() || undefined,
      page: pickerPage.value - 1,
      size: 10,
      sort: "cameraCode,asc"
    });
    if (requestId !== pickerRequestId || String(props.caseId) !== caseId || !pickerOpen.value) return;
    pickerRows.value = (result.data || []).map(mapCamera);
    pickerTotalPages.value = Math.max(1, result.meta?.totalPages || 0);
    pickerTotalCount.value = result.meta?.totalElements || 0;
  } catch (error) {
    if (requestId !== pickerRequestId || String(props.caseId) !== caseId || !pickerOpen.value) return;
    pickerRows.value = [];
    pickerTotalPages.value = 1;
    pickerTotalCount.value = 0;
    pickerError.value = readableError(error, "전체 카메라 목록을 불러오지 못했습니다.");
  } finally {
    if (requestId === pickerRequestId) pickerLoading.value = false;
  }
}

function openCameraPicker() {
  if (props.closed || mutationKind.value) return;
  pickerOpen.value = true;
  pickerSearchInput.value = "";
  pickerQuery.value = "";
  pickerPage.value = 1;
  selectedCameraIds.value = [];
  selectedWarningCameraIds.value = [];
  pickerMutationError.value = "";
  operationError.value = "";
  successMessage.value = "";
  loadPicker();
}

function closeCameraPicker() {
  if (mutationKind.value === "camera-add") return;
  pickerRequestId += 1;
  pickerOpen.value = false;
  pickerLoading.value = false;
  pickerError.value = "";
  pickerMutationError.value = "";
  selectedCameraIds.value = [];
  selectedWarningCameraIds.value = [];
}

function searchPicker() {
  pickerQuery.value = pickerSearchInput.value;
  pickerPage.value = 1;
  loadPicker();
}

function changePickerPage(page) {
  pickerPage.value = page;
  loadPicker();
}

function toggleCamera(camera) {
  if (activeCameraIds.value.has(camera.id)) return;
  if (selectedCameraIds.value.includes(camera.id)) {
    selectedCameraIds.value = selectedCameraIds.value.filter((id) => id !== camera.id);
    selectedWarningCameraIds.value = selectedWarningCameraIds.value.filter((id) => id !== camera.id);
    return;
  }
  selectedCameraIds.value = [...selectedCameraIds.value, camera.id];
  if (camera.status !== "online") {
    selectedWarningCameraIds.value = [...selectedWarningCameraIds.value, camera.id];
  }
}

async function addSelectedCameras() {
  if (props.closed || mutationKind.value || selectedCameraIds.value.length === 0) return;
  const actionId = ++mutationRequestId;
  const caseId = String(props.caseId);
  mutationKind.value = "camera-add";
  operationError.value = "";
  pickerMutationError.value = "";
  try {
    await addCaseCameras(caseId, selectedCameraIds.value);
    if (actionId !== mutationRequestId || String(props.caseId) !== caseId) return;
    mutationKind.value = "";
    closeCameraPicker();
    await reload();
    if (actionId === mutationRequestId && String(props.caseId) === caseId) {
      successMessage.value = "선택한 카메라를 사건에 추가했습니다.";
    }
  } catch (error) {
    await handleMutationFailure(error, "카메라를 추가하지 못했습니다.", actionId, caseId, "picker");
  } finally {
    if (actionId === mutationRequestId) mutationKind.value = "";
  }
}

async function removeCamera(camera) {
  if (props.closed || mutationKind.value) return;
  if (!globalThis.confirm?.(`${camera.cameraName || camera.cameraCode} 카메라를 사건에서 제외할까요?`)) return;
  const actionId = ++mutationRequestId;
  const caseId = String(props.caseId);
  mutationKind.value = "camera-remove";
  operationError.value = "";
  successMessage.value = "";
  try {
    await removeCaseCamera(caseId, camera.cameraId);
    if (actionId !== mutationRequestId || String(props.caseId) !== caseId) return;
    mutationKind.value = "";
    await reload();
    if (actionId === mutationRequestId && String(props.caseId) === caseId) {
      successMessage.value = "카메라를 사건에서 제외했습니다.";
    }
  } catch (error) {
    await handleMutationFailure(error, "카메라를 제외하지 못했습니다.", actionId, caseId);
  } finally {
    if (actionId === mutationRequestId) mutationKind.value = "";
  }
}

onBeforeUnmount(() => {
  setupRequestId += 1;
  mutationRequestId += 1;
  pickerRequestId += 1;
});
</script>

<template>
  <section class="search-setup-card" aria-labelledby="search-setup-title">
    <div class="section-heading search-setup-heading">
      <div>
        <h2 id="search-setup-title">실시간 탐색 설정</h2>
        <p>탐색 조건과 분석할 카메라를 사건별로 관리합니다.</p>
      </div>
      <span v-if="closed" class="readonly-chip">종료 사건 · 읽기 전용</span>
    </div>

    <div class="readiness-grid" :class="{ ready }">
      <div><span>실시간 사용 가능 조건</span><strong>{{ usableConditionCount }}개</strong></div>
      <div><span>활성 배정 카메라</span><strong>{{ activeCameraCount }}대</strong></div>
      <div>
        <span>탐색 시작 준비</span>
        <strong>{{ ready ? "준비 완료" : localLoading ? "확인 중" : "설정 필요" }}</strong>
      </div>
    </div>

    <p v-if="successMessage" class="setup-message success" role="status">{{ successMessage }}</p>
    <p v-if="operationError" class="setup-message error" role="alert">{{ operationError }}</p>

    <StateBlock :loading="localLoading" :error="localError" :empty="false" @retry="reload">
      <div class="setup-columns">
        <section ref="conditionsSection" class="setup-section" tabindex="-1" aria-labelledby="condition-heading">
          <div class="setup-section-heading">
            <div>
              <h3 id="condition-heading">탐색 조건</h3>
              <p>Jetson이 해석할 수 있는 구조화 조건만 준비 상태에 포함됩니다.</p>
            </div>
            <button v-if="!closed" type="button" class="ghost-button" :disabled="mutationBusy" @click="openCreateCondition">조건 추가</button>
          </div>

          <div v-if="localConditions.length === 0" class="setup-empty">
            <strong>등록된 탐색 조건이 없습니다.</strong>
            <button v-if="!closed" type="button" :disabled="mutationBusy" @click="openCreateCondition">첫 조건 추가하기</button>
          </div>
          <div v-else class="condition-list">
            <article v-for="condition in localConditions" :key="condition.id" class="condition-item">
              <div class="condition-title-row">
                <strong>{{ condition.normalizedPrompt || condition.prompt }}</strong>
                <span :class="['usability-badge', { usable: condition.realtimeUsable }]">
                  {{ condition.realtimeUsable ? "실시간 사용 가능" : "실시간 사용 불가" }}
                </span>
              </div>
              <p v-if="condition.normalizedExclusionPrompt">
                제외: {{ condition.normalizedExclusionPrompt }}
              </p>
              <p v-else-if="condition.exclusionPrompt" class="legacy-warning">
                기존 제외 조건을 해석할 수 없어 다시 저장해야 합니다.
              </p>
              <dl class="condition-meta">
                <div><dt>탐색 기간</dt><dd>{{ condition.searchStart ? `${formatKstDateTime(condition.searchStart)} ~ ${formatKstDateTime(condition.searchEnd)}` : "제한 없음" }}</dd></div>
                <div><dt>탐색 구역</dt><dd>{{ condition.searchArea || "전체" }}</dd></div>
              </dl>
              <p v-if="!condition.realtimeUsable" class="legacy-warning">
                구조화 입력으로 수정해야 실시간 탐색에 사용할 수 있습니다.
              </p>
              <div v-if="!closed" class="item-actions">
                <button type="button" class="ghost-button" :disabled="mutationBusy" @click="openEditCondition(condition)">수정</button>
                <button type="button" class="text-danger-button" :disabled="mutationBusy" @click="deleteCondition(condition)">삭제</button>
              </div>
            </article>
          </div>

          <form v-if="formOpen && !closed" class="condition-form" @submit.prevent="saveCondition">
            <div class="condition-form-heading">
              <h4>{{ editingConditionId === null ? "탐색 조건 추가" : "탐색 조건 수정" }}</h4>
              <button type="button" class="icon-close-button" aria-label="조건 입력 닫기" @click="closeConditionForm">×</button>
            </div>
            <p v-if="legacyEditWarning" class="legacy-warning">
              기존 문장을 구조화할 수 없습니다. 아래 항목을 모두 선택해 새 canonical 문장으로 저장해 주세요.
            </p>
            <fieldset>
              <legend>탐색 대상</legend>
              <div class="descriptor-grid">
                <label>성별<select v-model="conditionForm.subject.gender">
                  <option v-for="option in GENDER_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
                </select></label>
                <label>상의 색<select v-model="conditionForm.subject.upperColor">
                  <option value="">선택</option>
                  <option v-for="option in COLOR_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
                </select></label>
                <label>소매 길이<select v-model="conditionForm.subject.sleeve">
                  <option value="">선택</option>
                  <option v-for="option in SLEEVE_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
                </select></label>
                <label>하의 색<select v-model="conditionForm.subject.lowerColor">
                  <option value="">선택</option>
                  <option v-for="option in COLOR_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
                </select></label>
              </div>
              <p class="canonical-preview"><span>생성 문장</span>{{ canonicalPreview || "필수 항목을 모두 선택해 주세요." }}</p>
            </fieldset>

            <label class="checkbox-label">
              <input v-model="conditionForm.exclusionEnabled" type="checkbox" /> 제외 조건 사용
            </label>
            <fieldset v-if="conditionForm.exclusionEnabled">
              <legend>제외 대상</legend>
              <div class="descriptor-grid">
                <label>성별<select v-model="conditionForm.exclusion.gender">
                  <option v-for="option in GENDER_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
                </select></label>
                <label>상의 색<select v-model="conditionForm.exclusion.upperColor">
                  <option value="">선택</option>
                  <option v-for="option in COLOR_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
                </select></label>
                <label>소매 길이<select v-model="conditionForm.exclusion.sleeve">
                  <option value="">선택</option>
                  <option v-for="option in SLEEVE_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
                </select></label>
                <label>하의 색<select v-model="conditionForm.exclusion.lowerColor">
                  <option value="">선택</option>
                  <option v-for="option in COLOR_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
                </select></label>
              </div>
              <p class="canonical-preview"><span>제외 문장</span>{{ exclusionPreview || "필수 항목을 모두 선택해 주세요." }}</p>
            </fieldset>

            <div class="time-grid">
              <label>탐색 시작<input v-model="conditionForm.searchStart" type="datetime-local" step="0.001" /></label>
              <label>탐색 종료<input v-model="conditionForm.searchEnd" type="datetime-local" step="0.001" /></label>
            </div>
            <label class="area-field">탐색 구역 (선택)<input v-model="conditionForm.searchArea" maxlength="255" placeholder="예: 테헤란로 일대" /></label>
            <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
            <div class="form-actions">
              <button type="button" class="ghost-button" :disabled="mutationBusy" @click="closeConditionForm">취소</button>
              <button type="submit" class="primary-button" :disabled="mutationBusy">
                {{ mutationKind === "condition" ? "저장 중..." : "저장" }}
              </button>
            </div>
          </form>
        </section>

        <section ref="camerasSection" class="setup-section" tabindex="-1" aria-labelledby="camera-heading">
          <div class="setup-section-heading">
            <div>
              <h3 id="camera-heading">배정 카메라</h3>
              <p>활성 배정된 카메라 영상이 실시간 분석 대상이 됩니다.</p>
            </div>
            <button v-if="!closed" type="button" class="ghost-button" :disabled="mutationBusy" @click="openCameraPicker">카메라 추가</button>
          </div>

          <div v-if="localCameras.length === 0" class="setup-empty">
            <strong>배정된 카메라가 없습니다.</strong>
            <button v-if="!closed" type="button" :disabled="mutationBusy" @click="openCameraPicker">카메라 선택하기</button>
          </div>
          <div v-else class="assigned-camera-list">
            <article v-for="camera in localCameras" :key="camera.id" :class="['assigned-camera-item', { inactive: !camera.searchEnabled }]">
              <div>
                <strong>{{ camera.cameraName || "이름 없음" }}</strong>
                <span class="mono">{{ camera.cameraCode }}</span>
              </div>
              <span :class="['assignment-badge', { active: camera.searchEnabled }]">
                {{ camera.searchEnabled ? "활성" : "제외됨" }}
              </span>
              <button
                v-if="!closed && camera.searchEnabled"
                type="button"
                class="text-danger-button"
                :disabled="mutationBusy"
                @click="removeCamera(camera)"
              >제외</button>
            </article>
          </div>
        </section>
      </div>
    </StateBlock>
  </section>

  <div v-if="pickerOpen" class="modal-backdrop" @click.self="closeCameraPicker">
    <section class="modal camera-picker-modal" role="dialog" aria-modal="true" aria-labelledby="camera-picker-title">
      <div class="condition-form-heading">
        <div>
          <h3 id="camera-picker-title">사건 카메라 추가</h3>
          <p>연결 상태와 관계없이 선택할 수 있습니다.</p>
        </div>
        <button type="button" class="icon-close-button" aria-label="카메라 선택 닫기" @click="closeCameraPicker">×</button>
      </div>

      <form class="picker-search" @submit.prevent="searchPicker">
        <input v-model="pickerSearchInput" aria-label="카메라 검색" placeholder="카메라 코드 또는 이름" />
        <button type="submit" class="search-button">검색</button>
      </form>

      <StateBlock :loading="pickerLoading" :error="pickerError" :empty="pickerRows.length === 0" @retry="loadPicker">
        <div class="table-scroll picker-table-scroll">
          <table class="case-table picker-table">
            <thead><tr><th>선택</th><th>코드 / 이름</th><th>위치</th><th>Media Server</th><th>연결 상태</th></tr></thead>
            <tbody>
              <tr v-for="camera in pickerRows" :key="camera.id" :class="{ selected: selectedCameraIds.includes(camera.id) }">
                <td><input
                  type="checkbox"
                  :aria-label="`${camera.cameraCode} 선택`"
                  :checked="selectedCameraIds.includes(camera.id)"
                  :disabled="activeCameraIds.has(camera.id)"
                  @change="toggleCamera(camera)"
                /></td>
                <td><strong>{{ camera.cameraCode }}</strong><span>{{ camera.cameraName }}</span></td>
                <td>{{ camera.address }}</td>
                <td :title="camera.mediaServerCode">{{ camera.mediaServerName }}</td>
                <td>
                  <StatusBadge :status="camera.status" />
                  <small v-if="activeCameraIds.has(camera.id)">이미 활성 배정됨</small>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <BasePagination
          :page="pickerPage"
          :total-pages="pickerTotalPages"
          :total-count="pickerTotalCount"
          :disabled="pickerLoading"
          @update:page="changePickerPage"
        />
      </StateBlock>

      <p v-if="selectedWarningCount" class="picker-warning">
        연결 없음 또는 오류 상태인 카메라 {{ selectedWarningCount }}대를 선택했습니다. 배정은 가능하지만 현재 분석 영상이 수신되지 않을 수 있습니다.
      </p>
      <p v-if="pickerMutationError" class="setup-message error picker-operation-error" role="alert">
        {{ pickerMutationError }}
      </p>
      <div class="modal-actions">
        <button type="button" class="ghost-button" :disabled="mutationBusy" @click="closeCameraPicker">취소</button>
        <button
          type="button"
          class="primary-button"
          :disabled="selectedCameraIds.length === 0 || mutationBusy"
          @click="addSelectedCameras"
        >{{ mutationKind === "camera-add" ? "추가 중..." : `선택 ${selectedCameraIds.length}대 추가` }}</button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.search-setup-card { margin-top: 24px; border-top: 1px solid #e4e8ef; padding-top: 20px; }
.search-setup-heading { margin-bottom: 14px; }
.readonly-chip { border: 1px solid #d6dbe2; border-radius: 999px; padding: 5px 10px; background: #f1f3f5; color: #5b6472; font-size: 12px; font-weight: 800; }
.readiness-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin-bottom: 16px; }
.readiness-grid > div { display: grid; gap: 4px; border: 1px solid #ead38b; border-radius: 7px; padding: 11px 12px; background: #fffbeb; }
.readiness-grid.ready > div { border-color: #bbdfca; background: #eef8f2; }
.readiness-grid span { color: #64748b; font-size: 11px; font-weight: 700; }
.readiness-grid strong { color: #334155; font-size: 15px; }
.setup-message { margin: 0 0 12px; border-radius: 7px; padding: 9px 11px; font-size: 12px; font-weight: 700; }
.setup-message.success { border: 1px solid #bbdfca; background: #eef8f2; color: #2f6f54; }
.setup-message.error { border: 1px solid #efbcb6; background: #fff0ee; color: #9b382f; }
.setup-columns { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(280px, .8fr); gap: 14px; }
.setup-section { min-width: 0; border: 1px solid #e4e8ef; border-radius: 8px; padding: 14px; outline: none; }
.setup-section:focus { border-color: #5b9bb4; box-shadow: 0 0 0 3px rgba(65, 139, 168, .12); }
.setup-section-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 12px; }
.setup-section-heading h3 { margin: 0; font-size: 14px; }
.setup-section-heading p, .condition-form-heading p { margin: 4px 0 0; color: #64748b; font-size: 11px; line-height: 1.4; }
.setup-section-heading .ghost-button, .item-actions .ghost-button { margin-right: 0; white-space: nowrap; }
.setup-empty { min-height: 105px; display: grid; place-items: center; align-content: center; gap: 9px; border: 1px dashed #ccd5df; border-radius: 7px; color: #64748b; text-align: center; font-size: 12px; }
.setup-empty button { border: 0; background: transparent; color: #24708e; font-size: 12px; font-weight: 800; }
.condition-list, .assigned-camera-list { display: grid; gap: 8px; }
.condition-item { border: 1px solid #e4e8ef; border-radius: 7px; padding: 11px; }
.condition-title-row { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.condition-title-row > strong { color: #263646; font-size: 12px; line-height: 1.45; overflow-wrap: anywhere; }
.usability-badge, .assignment-badge { flex: 0 0 auto; border: 1px solid #efbcb6; border-radius: 999px; padding: 3px 7px; background: #fff0ee; color: #9b382f; font-size: 10px; font-weight: 800; }
.usability-badge.usable, .assignment-badge.active { border-color: #bbdfca; background: #e9f6ef; color: #2f6f54; }
.condition-item > p { margin: 7px 0 0; color: #64748b; font-size: 11px; line-height: 1.45; }
.condition-meta { display: grid; gap: 4px; margin: 9px 0 0; }
.condition-meta div { display: grid; grid-template-columns: 64px minmax(0, 1fr); gap: 8px; font-size: 11px; }
.condition-meta dt { color: #7b8794; font-weight: 700; }
.condition-meta dd { margin: 0; color: #475569; overflow-wrap: anywhere; }
.legacy-warning { color: #9b5f20 !important; }
.item-actions { display: flex; justify-content: flex-end; gap: 6px; margin-top: 10px; }
.text-danger-button { min-height: 32px; border: 1px solid #efbcb6; border-radius: 6px; padding: 5px 10px; background: #fff; color: #9b382f; font-size: 11px; font-weight: 800; }
.text-danger-button:disabled { opacity: .5; cursor: not-allowed; }
.condition-form { margin-top: 12px; border: 1px solid #b7cad4; border-radius: 8px; padding: 14px; background: #f8fbfc; }
.condition-form-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 12px; }
.condition-form-heading h3, .condition-form-heading h4 { margin: 0; }
.condition-form-heading h4 { font-size: 14px; }
.icon-close-button { width: 30px; height: 30px; border: 0; background: transparent; color: #64748b; font-size: 22px; line-height: 1; }
.condition-form fieldset { min-width: 0; margin: 0 0 12px; border: 1px solid #dbe3ea; border-radius: 7px; padding: 10px; background: #fff; }
.condition-form legend { padding: 0 5px; color: #475569; font-size: 11px; font-weight: 800; }
.descriptor-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px; }
.descriptor-grid label, .time-grid label, .area-field { display: grid; gap: 5px; color: #64748b; font-size: 11px; font-weight: 700; }
.canonical-preview { margin: 9px 0 0; border-radius: 6px; padding: 8px 9px; background: #eef4f7; color: #334155; font: 11px/1.45 "SFMono-Regular", Consolas, monospace; overflow-wrap: anywhere; }
.canonical-preview span { display: block; margin-bottom: 3px; color: #65808d; font-family: inherit; font-weight: 800; }
.checkbox-label { display: inline-flex; align-items: center; gap: 7px; margin: 0 0 10px; color: #475569; font-size: 12px; font-weight: 700; }
.time-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 9px; margin-bottom: 10px; }
.form-error { margin: 9px 0 0; color: #b42318; font-size: 11px; font-weight: 700; }
.assigned-camera-item { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: 8px; border: 1px solid #e4e8ef; border-radius: 7px; padding: 10px; }
.assigned-camera-item.inactive { background: #f8fafc; opacity: .72; }
.assigned-camera-item > div { min-width: 0; }
.assigned-camera-item strong, .assigned-camera-item .mono { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.assigned-camera-item strong { color: #334155; font-size: 12px; }
.assigned-camera-item .mono { margin-top: 3px; font-size: 10px; }
.camera-picker-modal { width: min(960px, 100%); max-height: calc(100vh - 40px); overflow: auto; }
.picker-search { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; margin-bottom: 12px; }
.picker-table-scroll { max-height: 390px; overflow: auto; }
.picker-table { min-width: 760px; }
.picker-table th:first-child, .picker-table td:first-child { width: 54px; text-align: center; }
.picker-table tr.selected { background: #eef8fb; }
.picker-table td strong, .picker-table td span, .picker-table td small { display: block; }
.picker-table td span, .picker-table td small { margin-top: 3px; color: #64748b; font-size: 11px; }
.picker-warning { margin: 12px 0 0; border: 1px solid #ead38b; border-radius: 7px; padding: 9px 10px; background: #fffbeb; color: #7a5a18; font-size: 11px; font-weight: 700; }
.picker-operation-error { margin-top: 12px; margin-bottom: 0; }

@media (max-width: 1100px) {
  .setup-columns { grid-template-columns: 1fr; }
}
</style>
