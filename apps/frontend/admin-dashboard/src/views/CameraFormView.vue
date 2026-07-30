<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { getCamera, updateCameraName } from "../api/cameraApi";
import LiveStreamPlayer from "../components/LiveStreamPlayer.vue";
import StateBlock from "../components/common/StateBlock.vue";
import StatusBadge from "../components/common/StatusBadge.vue";
import { buildCameraPlaybackUrl, mapCamera } from "../domain/cameraMapper";

const router = useRouter();
const route = useRoute();
const isEditMode = computed(() => Boolean(route.params.cameraId));
const item = ref(null);
const form = reactive({ cameraName: "" });
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
let submitRequestId = 0;

const playbackUrl = computed(() => item.value?.cameraCode
  ? buildCameraPlaybackUrl(item.value.cameraCode)
  : "");

const load = async () => {
  if (!isEditMode.value) {
    item.value = null;
    loading.value = false;
    loadError.value = "";
    notFound.value = false;
    return;
  }

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
    form.cameraName = camera.cameraName;
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

const save = async () => {
  if (!item.value || submitting.value) return;
  const cameraName = form.cameraName.trim();
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

watch(() => route.params.cameraId, load, { immediate: true });
onBeforeUnmount(() => {
  loadRequestId += 1;
  submitRequestId += 1;
});
</script>

<template>
  <section class="content-panel form-page wide-form-page">
    <div class="section-heading">
      <div>
        <h2>{{ isEditMode ? "CCTV 수정" : "CCTV 등록" }}</h2>
        <p>{{ isEditMode ? "등록된 CCTV 정보를 확인하고 이름을 수정합니다." : "신규 등록 API 의존성이 준비되지 않았습니다." }}</p>
      </div>
    </div>

    <div v-if="!isEditMode" class="state-view">
      <strong>신규 CCTV 등록은 현재 비활성화되어 있습니다.</strong>
      <p>Media Server 목록 API가 연결되면 이 화면에서 등록할 수 있습니다.</p>
      <button class="ghost-button" type="button" @click="router.push('/admin/cameras')">목록으로</button>
    </div>

    <div v-else-if="notFound" class="state-view error">
      <strong>존재하지 않는 CCTV입니다.</strong>
      <button type="button" @click="router.push('/admin/cameras')">목록으로</button>
    </div>

    <StateBlock v-else :loading="loading" :error="loadError" :empty="!item" @retry="load">
      <div class="form-grid camera-form-grid">
        <section>
          <h3>기본 정보</h3>
          <label>CCTV 코드<input :value="item?.cameraCode" disabled /><small>카메라 코드는 수정할 수 없습니다.</small></label>
          <label>CCTV 이름<input v-model="form.cameraName" :disabled="submitting" /><small>{{ nameError }}</small></label>
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
        <button class="primary-button" type="button" :disabled="submitting" @click="save">
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
