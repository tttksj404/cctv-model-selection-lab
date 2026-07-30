<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { Grid2X2, Minimize2 } from "lucide-vue-next";
import { listCameras } from "../api/cameraApi";
import LiveStreamPlayer from "../components/LiveStreamPlayer.vue";
import { buildCameraPlaybackUrl, mapCamera } from "../domain/cameraMapper";

const createEmptySlots = () => Array.from({ length: 4 }, (_, index) => ({
  id: `empty-${index + 1}`,
  empty: true
}));

const streams = ref(createEmptySlots());
const loading = ref(true);
const error = ref("");
const playbackStates = ref({});
const openedInfoId = ref(null);
const gridRef = ref(null);
const isQuadFullscreen = ref(false);
let latestRequestId = 0;

const load = async () => {
  const requestId = ++latestRequestId;
  loading.value = true;
  error.value = "";
  openedInfoId.value = null;

  try {
    const result = await listCameras({ page: 0, size: 4, sort: "cameraCode,asc" });
    if (requestId !== latestRequestId) return;
    const cameras = (result.data || []).map(mapCamera).map((camera) => ({
      ...camera,
      protocol: "HLS",
      url: buildCameraPlaybackUrl(camera.cameraCode),
      empty: false
    }));
    streams.value = [...cameras, ...createEmptySlots()].slice(0, 4);
    playbackStates.value = Object.fromEntries(cameras.map((camera) => [camera.id, "loading"]));
  } catch (cause) {
    if (requestId !== latestRequestId) return;
    streams.value = createEmptySlots();
    error.value = cause?.message || "실시간 CCTV 목록을 불러오지 못했습니다.";
  } finally {
    if (requestId === latestRequestId) loading.value = false;
  }
};

const toggleInfo = (streamId) => {
  openedInfoId.value = openedInfoId.value === streamId ? null : streamId;
};

const setPlaybackState = (streamId, state) => {
  playbackStates.value[streamId] = state;
};

const playbackStateLabel = (streamId) => ({
  loading: "연결 확인 중",
  ready: "플레이어 로드됨",
  error: "재생 오류"
})[playbackStates.value[streamId]] || "확인 전";

const updateQuadFullscreenState = () => {
  isQuadFullscreen.value = document.fullscreenElement === gridRef.value;
};

const toggleQuadFullscreen = async () => {
  if (!gridRef.value) return;
  if (document.fullscreenElement === gridRef.value) await document.exitFullscreen();
  else await gridRef.value.requestFullscreen();
};

onMounted(() => {
  load();
  document.addEventListener("fullscreenchange", updateQuadFullscreenState);
  window.addEventListener("toggle-live-quad", toggleQuadFullscreen);
});

onBeforeUnmount(() => {
  latestRequestId += 1;
  document.removeEventListener("fullscreenchange", updateQuadFullscreenState);
  window.removeEventListener("toggle-live-quad", toggleQuadFullscreen);
});
</script>

<template>
  <section class="live-monitoring-page">
    <div v-if="loading || error" :class="['live-monitoring-notice', error && 'error']">
      <span>{{ loading ? "CCTV 정보를 불러오는 중입니다." : error }}</span>
      <button v-if="error" type="button" @click="load">다시 시도</button>
    </div>

    <div ref="gridRef" class="live-stream-grid">
      <div class="quad-view-toolbar">
        <button type="button" @click="toggleQuadFullscreen">
          <Minimize2 v-if="isQuadFullscreen" :size="14" />
          <Grid2X2 v-else :size="14" />
          <span>{{ isQuadFullscreen ? "4분할 보기 닫기" : "4분할 보기" }}</span>
        </button>
      </div>

      <article
        v-for="stream in streams"
        :key="stream.id"
        :class="['live-stream-card', stream.empty && 'is-empty', openedInfoId === stream.id && 'is-info-open']"
      >
        <div v-if="stream.empty" class="empty-camera-slot">
          <strong>카메라 미연결</strong>
          <span>{{ loading ? "등록된 CCTV를 확인하고 있습니다." : "현재 연결할 CCTV가 없습니다." }}</span>
        </div>

        <template v-else>
          <div class="live-stream-frame">
            <LiveStreamPlayer
              :protocol="stream.protocol"
              :url="stream.url"
              @info="toggleInfo(stream.id)"
              @state-change="setPlaybackState(stream.id, $event)"
            />
            <div class="stream-label"><strong>{{ stream.cameraName }}</strong></div>
            <div class="stream-playback-state" :class="playbackStates[stream.id]">
              {{ playbackStateLabel(stream.id) }}
            </div>
          </div>

          <aside v-if="openedInfoId === stream.id" class="stream-info-panel">
            <div class="stream-info-heading">
              <div><span>실시간 CCTV 정보</span><strong>{{ stream.cameraName }}</strong></div>
              <button type="button" aria-label="정보 패널 닫기" @click="openedInfoId = null">×</button>
            </div>
            <dl>
              <div><dt>카메라 코드</dt><dd>{{ stream.cameraCode }}</dd></div>
              <div><dt>카메라 이름</dt><dd>{{ stream.cameraName }}</dd></div>
              <div><dt>위도</dt><dd>{{ stream.latitude }}</dd></div>
              <div><dt>경도</dt><dd>{{ stream.longitude }}</dd></div>
              <div><dt>설치 주소</dt><dd>{{ stream.address }}</dd></div>
              <div><dt>Media Server</dt><dd>{{ stream.mediaServerName }} ({{ stream.mediaServerCode }})</dd></div>
              <div><dt>DB 상태</dt><dd :class="['stream-status', stream.status]"><i /> {{ stream.statusCode }}</dd></div>
              <div><dt>마지막 Heartbeat</dt><dd>{{ stream.lastHeartbeat }}</dd></div>
              <div><dt>재생 상태</dt><dd>{{ playbackStateLabel(stream.id) }}</dd></div>
            </dl>
          </aside>
        </template>
      </article>
    </div>
  </section>
</template>
