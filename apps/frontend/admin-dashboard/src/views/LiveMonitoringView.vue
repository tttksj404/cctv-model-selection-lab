<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { Grid2X2, Maximize2, Minimize2 } from "lucide-vue-next";
import LiveStreamPlayer from "../components/LiveStreamPlayer.vue";

const streams = [
  {
    id: "webrtc-camera-01",
    cameraName: "CCTV-01",
    protocol: "WebRTC",
    url: "http://70.12.108.93:8889/camera-01/whep",
    latitude: "37.5010000",
    longitude: "127.0390000",
    address: "강남구 테헤란로 152",
    status: "ONLINE",
    lastHeartbeat: "09:52:11"
  },
  {
    id: "empty-top-right",
    empty: true
  },
  {
    id: "empty-bottom-left",
    empty: true
  },
  {
    id: "webrtc-camera-04",
    cameraName: "CCTV-04",
    protocol: "WebRTC",
    url: "http://70.12.108.93:8889/camera-04/whep",
    latitude: "37.5080000",
    longitude: "127.0350000",
    address: "강남구 봉은사로 78",
    status: "ONLINE",
    lastHeartbeat: "09:41:33"
  }
];

const openedInfoId = ref(null);
const gridRef = ref(null);
const isQuadFullscreen = ref(false);

const toggleInfo = (streamId) => {
  openedInfoId.value = openedInfoId.value === streamId ? null : streamId;
};

const updateQuadFullscreenState = () => {
  isQuadFullscreen.value = document.fullscreenElement === gridRef.value;
};

const toggleQuadFullscreen = async () => {
  if (!gridRef.value) return;

  if (document.fullscreenElement === gridRef.value) {
    await document.exitFullscreen();
  } else {
    await gridRef.value.requestFullscreen();
  }
};

onMounted(() => {
  document.addEventListener("fullscreenchange", updateQuadFullscreenState);
  window.addEventListener("toggle-live-quad", toggleQuadFullscreen);
});

onBeforeUnmount(() => {
  document.removeEventListener("fullscreenchange", updateQuadFullscreenState);
  window.removeEventListener("toggle-live-quad", toggleQuadFullscreen);
});
</script>

<template>
  <section class="live-monitoring-page">
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
          <span>현재 연결된 실시간 스트림이 없습니다.</span>
        </div>

        <template v-else>
          <div class="live-stream-frame">
            <LiveStreamPlayer
              :protocol="stream.protocol"
              :url="stream.url"
              @info="toggleInfo(stream.id)"
            />
            <div class="stream-label">
              <strong>{{ stream.cameraName }}</strong>
            </div>
          </div>

          <aside v-if="openedInfoId === stream.id" class="stream-info-panel">
            <div class="stream-info-heading">
              <div>
                <span>실시간 CCTV 정보</span>
                <strong>{{ stream.cameraName }}</strong>
              </div>
              <button type="button" aria-label="정보 패널 닫기" @click="openedInfoId = null">×</button>
            </div>

            <dl>
              <div>
                <dt>카메라 이름</dt>
                <dd>{{ stream.cameraName }}</dd>
              </div>
              <div>
                <dt>위도</dt>
                <dd>{{ stream.latitude }}</dd>
              </div>
              <div>
                <dt>경도</dt>
                <dd>{{ stream.longitude }}</dd>
              </div>
              <div>
                <dt>설치 주소</dt>
                <dd>{{ stream.address }}</dd>
              </div>
              <div>
                <dt>상태</dt>
                <dd class="stream-status"><i /> {{ stream.status }}</dd>
              </div>
              <div>
                <dt>마지막 Heartbeat</dt>
                <dd>{{ stream.lastHeartbeat }}</dd>
              </div>
            </dl>
          </aside>
        </template>
      </article>
    </div>
  </section>
</template>
