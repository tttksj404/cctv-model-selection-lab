<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  createCamera,
  getCamera,
  listMediaServerOptions,
  updateCameraName
} from "../api/cameraApi";
import LiveStreamPlayer from "../components/LiveStreamPlayer.vue";
import StateBlock from "../components/common/StateBlock.vue";
import StatusBadge from "../components/common/StatusBadge.vue";
import { buildCameraPlaybackUrl, mapCamera } from "../domain/cameraMapper";

const router = useRouter();
const route = useRoute();
const CAMERA_CODE_PATTERN = /^[A-Za-z0-9._-]+$/;
const isEditMode = computed(() => Boolean(route.params.cameraId));
const item = ref(null);
const editForm = reactive({ cameraName: "" });
const createForm = reactive({
  mediaServerId: "",
  cameraCode: "",
  cameraName: "",
  latitude: "",
  longitude: "",
  address: "",
  rtspUrl: ""
});
const createErrors = reactive({
  mediaServerId: "",
  cameraCode: "",
  cameraName: "",
  latitude: "",
  longitude: "",
  address: "",
  rtspUrl: ""
});
const mediaServerOptions = ref([]);
const optionsLoading = ref(false);
const optionsError = ref("");
const initialName = ref("");
const loading = ref(false);
const loadError = ref("");
const notFound = ref(false);
const submitting = ref(false);
const operationError = ref("");
const nameError = ref("");
const streamTestOpen = ref(false);
const playbackState = ref("loading");
let loadRequestId = 0;
let optionsRequestId = 0;
let submitRequestId = 0;

const playbackUrl = computed(() => item.value?.cameraCode
  ? buildCameraPlaybackUrl(item.value.cameraCode)
  : "");

const clearCreateFieldError = (field) => {
  createErrors[field] = "";
  operationError.value = "";
};

const clearCreateErrors = () => {
  Object.keys(createErrors).forEach((field) => {
    createErrors[field] = "";
  });
  operationError.value = "";
};

const loadMediaServers = async () => {
  const requestId = ++optionsRequestId;
  optionsLoading.value = true;
  optionsError.value = "";

  try {
    const options = await listMediaServerOptions();
    if (requestId !== optionsRequestId || isEditMode.value) return;
    mediaServerOptions.value = Array.isArray(options) ? options : [];

    const selectedId = Number(createForm.mediaServerId);
    if (
      createForm.mediaServerId !== ""
        && !mediaServerOptions.value.some((option) => Number(option.id) === selectedId)
    ) {
      createForm.mediaServerId = "";
    }
  } catch (cause) {
    if (requestId !== optionsRequestId || isEditMode.value) return;
    mediaServerOptions.value = [];
    optionsError.value = cause?.message || "Media Server 목록을 불러오지 못했습니다.";
  } finally {
    if (requestId === optionsRequestId && !isEditMode.value) optionsLoading.value = false;
  }
};

const load = async () => {
  if (!isEditMode.value) {
    loadRequestId += 1;
    item.value = null;
    loading.value = false;
    loadError.value = "";
    notFound.value = false;
    operationError.value = "";
    nameError.value = "";
    await loadMediaServers();
    return;
  }

  optionsRequestId += 1;
  optionsLoading.value = false;
  optionsError.value = "";
  const cameraId = String(route.params.cameraId);
  const requestId = ++loadRequestId;
  loading.value = true;
  loadError.value = "";
  notFound.value = false;
  operationError.value = "";

  try {
    const camera = mapCamera(await getCamera(cameraId));
    if (requestId !== loadRequestId || String(route.params.cameraId) !== cameraId) return;
    item.value = camera;
    editForm.cameraName = camera.cameraName;
    initialName.value = camera.cameraName;
  } catch (cause) {
    if (requestId !== loadRequestId || String(route.params.cameraId) !== cameraId) return;
    item.value = null;
    if (cause?.status === 404) notFound.value = true;
    else loadError.value = cause?.message || "CCTV 정보를 불러오지 못했습니다.";
  } finally {
    if (requestId === loadRequestId && String(route.params.cameraId) === cameraId) loading.value = false;
  }
};

const validateCreateForm = () => {
  clearCreateErrors();

  const mediaServerIdText = String(createForm.mediaServerId).trim();
  const cameraCode = createForm.cameraCode.trim();
  const cameraName = createForm.cameraName.trim();
  const latitudeText = String(createForm.latitude).trim();
  const longitudeText = String(createForm.longitude).trim();
  const address = createForm.address.trim();
  const rtspUrl = createForm.rtspUrl.trim();
  const mediaServerId = Number(mediaServerIdText);
  const latitude = Number(latitudeText);
  const longitude = Number(longitudeText);

  Object.assign(createForm, { cameraCode, cameraName, address, rtspUrl });

  if (!mediaServerIdText) createErrors.mediaServerId = "Media Server를 선택해 주세요.";
  else if (!Number.isInteger(mediaServerId) || mediaServerId <= 0) {
    createErrors.mediaServerId = "올바른 Media Server를 선택해 주세요.";
  }

  if (!cameraCode) createErrors.cameraCode = "CCTV 코드를 입력해 주세요.";
  else if (cameraCode.length > 100) createErrors.cameraCode = "CCTV 코드는 100자 이하로 입력해 주세요.";
  else if (!CAMERA_CODE_PATTERN.test(cameraCode)) {
    createErrors.cameraCode = "CCTV 코드는 영문, 숫자, 마침표, 밑줄, 하이픈만 사용할 수 있습니다.";
  }

  if (!cameraName) createErrors.cameraName = "CCTV 이름을 입력해 주세요.";
  else if (cameraName.length > 100) createErrors.cameraName = "CCTV 이름은 100자 이하로 입력해 주세요.";

  if (!latitudeText) createErrors.latitude = "위도를 입력해 주세요.";
  else if (!Number.isFinite(latitude) || latitude < -90 || latitude > 90) {
    createErrors.latitude = "위도는 -90 이상 90 이하의 숫자로 입력해 주세요.";
  }

  if (!longitudeText) createErrors.longitude = "경도를 입력해 주세요.";
  else if (!Number.isFinite(longitude) || longitude < -180 || longitude > 180) {
    createErrors.longitude = "경도는 -180 이상 180 이하의 숫자로 입력해 주세요.";
  }

  if (!address) createErrors.address = "설치 주소를 입력해 주세요.";
  else if (address.length > 255) createErrors.address = "설치 주소는 255자 이하로 입력해 주세요.";

  if (!rtspUrl) createErrors.rtspUrl = "RTSP URL을 입력해 주세요.";
  else if (rtspUrl.length > 500) createErrors.rtspUrl = "RTSP URL은 500자 이하로 입력해 주세요.";

  if (Object.values(createErrors).some(Boolean)) return null;
  return { mediaServerId, cameraCode, cameraName, latitude, longitude, address, rtspUrl };
};

const saveCreate = async () => {
  if (submitting.value || optionsLoading.value || optionsError.value || mediaServerOptions.value.length === 0) return;
  const payload = validateCreateForm();
  if (!payload) return;

  const requestId = ++submitRequestId;
  submitting.value = true;
  try {
    const created = await createCamera(payload);
    if (requestId !== submitRequestId || isEditMode.value) return;
    if (created?.id === null || created?.id === undefined) {
      operationError.value = "등록 결과에서 CCTV ID를 확인하지 못했습니다.";
      return;
    }
    await router.push(`/admin/cameras/${created.id}/edit`);
  } catch (cause) {
    if (requestId !== submitRequestId || isEditMode.value) return;

    if (cause?.status === 409 && cause?.code === "DUPLICATE_RESOURCE") {
      createErrors.cameraCode = "이미 등록된 CCTV 코드입니다.";
    } else if (cause?.status === 404 && cause?.code === "RESOURCE_NOT_FOUND") {
      createErrors.mediaServerId = "선택한 Media Server를 찾을 수 없습니다. 다시 선택해 주세요.";
      await loadMediaServers();
    } else {
      operationError.value = cause?.message || "CCTV를 등록하지 못했습니다.";
    }
  } finally {
    if (requestId === submitRequestId) submitting.value = false;
  }
};

const saveEdit = async () => {
  if (!item.value || submitting.value) return;
  const cameraName = editForm.cameraName.trim();
  nameError.value = "";
  operationError.value = "";

  if (!cameraName) {
    nameError.value = "CCTV 이름을 입력해 주세요.";
    return;
  }
  if (cameraName.length > 100) {
    nameError.value = "CCTV 이름은 100자 이하로 입력해 주세요.";
    return;
  }
  if (cameraName === initialName.value) {
    await router.push("/admin/cameras");
    return;
  }

  const cameraId = String(route.params.cameraId);
  const requestId = ++submitRequestId;
  submitting.value = true;
  try {
    await updateCameraName(cameraId, cameraName);
    if (requestId !== submitRequestId || String(route.params.cameraId) !== cameraId) return;
    await router.push("/admin/cameras");
  } catch (cause) {
    if (requestId !== submitRequestId || String(route.params.cameraId) !== cameraId) return;
    operationError.value = cause?.message || "CCTV 이름을 수정하지 못했습니다.";
  } finally {
    if (requestId === submitRequestId && String(route.params.cameraId) === cameraId) submitting.value = false;
  }
};

const openStreamTest = () => {
  playbackState.value = "loading";
  streamTestOpen.value = true;
};

watch(() => route.params.cameraId, () => {
  submitRequestId += 1;
  submitting.value = false;
  load();
}, { immediate: true });
onBeforeUnmount(() => {
  loadRequestId += 1;
  optionsRequestId += 1;
  submitRequestId += 1;
});
</script>

<template>
  <section class="content-panel form-page wide-form-page">
    <div class="section-heading">
      <div>
        <h2>{{ isEditMode ? "CCTV 수정" : "CCTV 등록" }}</h2>
        <p>{{ isEditMode ? "등록된 CCTV 정보를 확인하고 이름을 수정합니다." : "CCTV 설치 정보와 스트림 연결 정보를 등록합니다." }}</p>
      </div>
    </div>

    <template v-if="!isEditMode">
      <div v-if="optionsLoading" class="state-view">
        <strong>Media Server 목록을 불러오는 중입니다.</strong>
      </div>
      <div v-else-if="optionsError" class="state-view error">
        <strong>{{ optionsError }}</strong>
        <button type="button" @click="loadMediaServers">다시 시도</button>
      </div>
      <div v-else-if="mediaServerOptions.length === 0" class="state-view">
        <strong>등록 가능한 Media Server가 없습니다.</strong>
        <p>ACTIVE 상태의 Media Server를 먼저 준비한 뒤 다시 조회해 주세요.</p>
        <button type="button" @click="loadMediaServers">다시 조회</button>
      </div>
      <form v-else novalidate @submit.prevent="saveCreate">
        <div class="form-grid camera-form-grid">
          <section>
            <h3>기본 정보</h3>
            <label class="required-field">
              <span class="field-title">Media Server</span>
              <select
                v-model="createForm.mediaServerId"
                name="mediaServerId"
                required
                :disabled="submitting"
                :aria-invalid="Boolean(createErrors.mediaServerId)"
                @change="clearCreateFieldError('mediaServerId')"
              >
                <option value="" disabled>Media Server 선택</option>
                <option v-for="server in mediaServerOptions" :key="server.id" :value="server.id">
                  {{ server.name }} ({{ server.serverCode }})
                </option>
              </select>
              <small>{{ createErrors.mediaServerId }}</small>
            </label>
            <label class="required-field camera-code-field">
              <span class="field-title">CCTV 코드</span>
              <input
                v-model="createForm.cameraCode"
                name="cameraCode"
                maxlength="100"
                pattern="[A-Za-z0-9._-]+"
                autocomplete="off"
                required
                :disabled="submitting"
                :aria-invalid="Boolean(createErrors.cameraCode)"
                placeholder="camera-03"
                @input="clearCreateFieldError('cameraCode')"
              />
              <small :class="{ 'camera-field-help': !createErrors.cameraCode }">
                {{ createErrors.cameraCode || "MediaMTX 경로명과 대소문자까지 정확히 일치해야 합니다." }}
              </small>
            </label>
            <label class="required-field">
              <span class="field-title">CCTV 이름</span>
              <input
                v-model="createForm.cameraName"
                name="cameraName"
                maxlength="100"
                autocomplete="off"
                required
                :disabled="submitting"
                :aria-invalid="Boolean(createErrors.cameraName)"
                placeholder="3번 카메라"
                @input="clearCreateFieldError('cameraName')"
              />
              <small>{{ createErrors.cameraName }}</small>
            </label>
            <label class="required-field">
              <span class="field-title">설치 주소</span>
              <input
                v-model="createForm.address"
                name="address"
                maxlength="255"
                autocomplete="street-address"
                required
                :disabled="submitting"
                :aria-invalid="Boolean(createErrors.address)"
                placeholder="설치 주소"
                @input="clearCreateFieldError('address')"
              />
              <small>{{ createErrors.address }}</small>
            </label>
          </section>
          <section>
            <h3>좌표 및 연결</h3>
            <label class="required-field">
              <span class="field-title">위도</span>
              <input
                v-model="createForm.latitude"
                name="latitude"
                type="number"
                min="-90"
                max="90"
                step="any"
                required
                :disabled="submitting"
                :aria-invalid="Boolean(createErrors.latitude)"
                placeholder="37.5"
                @input="clearCreateFieldError('latitude')"
              />
              <small>{{ createErrors.latitude }}</small>
            </label>
            <label class="required-field">
              <span class="field-title">경도</span>
              <input
                v-model="createForm.longitude"
                name="longitude"
                type="number"
                min="-180"
                max="180"
                step="any"
                required
                :disabled="submitting"
                :aria-invalid="Boolean(createErrors.longitude)"
                placeholder="127.0"
                @input="clearCreateFieldError('longitude')"
              />
              <small>{{ createErrors.longitude }}</small>
            </label>
            <label class="required-field camera-rtsp-field">
              <span class="field-title">RTSP URL</span>
              <input
                v-model="createForm.rtspUrl"
                name="rtspUrl"
                maxlength="500"
                autocomplete="off"
                required
                :disabled="submitting"
                :aria-invalid="Boolean(createErrors.rtspUrl)"
                placeholder="rtsp://camera-source/stream"
                @input="clearCreateFieldError('rtspUrl')"
              />
              <small>{{ createErrors.rtspUrl }}</small>
            </label>
          </section>
        </div>
        <p v-if="operationError" class="form-error camera-operation-error" role="alert">{{ operationError }}</p>
        <div class="form-actions">
          <button class="ghost-button" type="button" :disabled="submitting" @click="router.back()">취소</button>
          <button class="primary-button" type="submit" :disabled="submitting">
            {{ submitting ? "등록 중" : "CCTV 등록" }}
          </button>
        </div>
      </form>
    </template>

    <div v-else-if="notFound" class="state-view error">
      <strong>존재하지 않는 CCTV입니다.</strong>
      <button type="button" @click="router.push('/admin/cameras')">목록으로</button>
    </div>

    <StateBlock v-else :loading="loading" :error="loadError" :empty="!item" @retry="load">
      <div class="form-grid camera-form-grid">
        <section>
          <h3>기본 정보</h3>
          <label>CCTV 코드<input :value="item?.cameraCode" disabled /><small>카메라 코드는 수정할 수 없습니다.</small></label>
          <label>CCTV 이름<input v-model="editForm.cameraName" :disabled="submitting" /><small>{{ nameError }}</small></label>
          <label>설치 위치<input :value="item?.address" disabled /><small></small></label>
          <label>Media Server<input :value="`${item?.mediaServerName} (${item?.mediaServerCode})`" disabled /><small></small></label>
        </section>
        <section>
          <h3>좌표 및 연결</h3>
          <label>위도<input :value="item?.latitude" disabled /><small></small></label>
          <label>경도<input :value="item?.longitude" disabled /><small></small></label>
          <label>마지막 Heartbeat<input :value="item?.lastHeartbeat" disabled /><small></small></label>
          <label>DB 상태<span class="camera-form-status"><StatusBadge :status="item?.status" /></span><small>스트림 재생 상태와 별도로 관리됩니다.</small></label>
          <button class="ghost-button" type="button" @click="openStreamTest">실시간 스트림 미리보기</button>
        </section>
        <section class="wide camera-readonly-notice">
          <h3>수정 제한 안내</h3>
          <p>스트림 URL은 보안상 조회 응답에 포함되지 않습니다. 현재 화면에서는 이름만 수정하며 좌표·주소·소속 변경은 제공하지 않습니다.</p>
        </section>
      </div>
      <p v-if="operationError" class="form-error camera-operation-error">{{ operationError }}</p>
      <div class="form-actions">
        <button class="ghost-button" type="button" :disabled="submitting" @click="router.back()">취소</button>
        <button class="primary-button" type="button" :disabled="submitting" @click="saveEdit">
          {{ submitting ? "저장 중" : "이름 저장" }}
        </button>
      </div>
    </StateBlock>

    <div v-if="streamTestOpen" class="modal-backdrop" @click.self="streamTestOpen = false">
      <section class="modal stream-test-modal">
        <div class="section-heading">
          <div><h3>실시간 스트림 미리보기</h3><p>DB 상태와 별개로 MediaMTX 재생 화면을 확인합니다.</p></div>
          <button class="ghost-button" type="button" @click="streamTestOpen = false">닫기</button>
        </div>
        <div class="stream-preview camera-stream-preview">
          <LiveStreamPlayer protocol="HLS" :url="playbackUrl" @state-change="playbackState = $event" />
        </div>
        <div class="stream-signal">
          <div class="signal-bars"><i v-for="level in 4" :key="level" :class="{ active: playbackState === 'ready' }" :style="{ height: `${level * 7}px` }" /></div>
          <strong>{{ playbackState === "ready" ? "플레이어 로드됨" : playbackState === "error" ? "재생 오류" : "연결 확인 중" }}</strong>
          <span>이 표시는 카메라의 DB ONLINE/OFFLINE 상태를 변경하지 않습니다.</span>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.camera-code-field { grid-template-rows: auto auto minmax(14px, auto); }
.camera-field-help { color: #64748b; line-height: 1.45; }
</style>
