<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import Hls from "hls.js";
import { Info, Maximize2, Minimize2, Pause, PictureInPicture2, Play } from "lucide-vue-next";

const emit = defineEmits(["info", "state-change"]);

const props = defineProps({
  protocol: { type: String, required: true },
  url: { type: String, required: true }
});

const videoRef = ref(null);
const playerRoot = ref(null);
const state = ref("loading");
const isPlaying = ref(false);
const pipSupported = ref(false);
const isFullscreen = ref(false);
let peerConnection = null;
let hls = null;

const setState = (nextState) => {
  state.value = nextState;
  emit("state-change", nextState);
};

const updateFullscreenState = () => {
  const card = playerRoot.value?.closest(".live-stream-card");
  isFullscreen.value = Boolean(card && document.fullscreenElement === card);
};

const waitForIceGathering = () => new Promise((resolve) => {
  if (peerConnection.iceGatheringState === "complete") {
    resolve();
    return;
  }

  const checkState = () => {
    if (peerConnection.iceGatheringState === "complete") {
      peerConnection.removeEventListener("icegatheringstatechange", checkState);
      resolve();
    }
  };

  peerConnection.addEventListener("icegatheringstatechange", checkState);
});

const markPlaying = () => {
  setState("ready");
  isPlaying.value = true;
};

const markPaused = () => {
  isPlaying.value = false;
};

const disposeHls = () => {
  hls?.destroy();
  hls = null;
};

const startHls = async () => {
  const video = videoRef.value;
  if (!video) return;

  disposeHls();

  if (video.canPlayType("application/vnd.apple.mpegurl")) {
    video.src = props.url;
    await video.play();
    return;
  }

  if (!Hls.isSupported()) {
    throw new Error("HLS를 재생할 수 없는 브라우저입니다.");
  }

  hls = new Hls();
  hls.on(Hls.Events.ERROR, (_event, data) => {
    if (data.fatal) setState("error");
  });
  hls.on(Hls.Events.MANIFEST_PARSED, () => {
    video.play().catch(() => setState("error"));
  });
  hls.loadSource(props.url);
  hls.attachMedia(video);
};

const startWebRtc = async () => {
  const video = videoRef.value;
  peerConnection = new RTCPeerConnection();
  peerConnection.addTransceiver("video", { direction: "recvonly" });

  peerConnection.ontrack = (event) => {
    video.srcObject = event.streams[0];
  };

  peerConnection.onconnectionstatechange = () => {
    if (["failed", "disconnected", "closed"].includes(peerConnection.connectionState)) {
      setState("error");
    }
  };

  await peerConnection.setLocalDescription(await peerConnection.createOffer());
  await waitForIceGathering();

  const response = await fetch(props.url, {
    method: "POST",
    headers: { "Content-Type": "application/sdp" },
    body: peerConnection.localDescription.sdp
  });

  if (!response.ok) {
    throw new Error(`WebRTC 연결 실패 (${response.status})`);
  }

  await peerConnection.setRemoteDescription({
    type: "answer",
    sdp: await response.text()
  });

  await video.play();
};

const start = async () => {
  setState("loading");

  try {
    if (props.protocol === "HLS") await startHls();
    else await startWebRtc();
  } catch (error) {
    console.error(`[${props.protocol}] stream error`, error);
    setState("error");
  }
};

const togglePlay = async () => {
  if (!videoRef.value) return;

  if (videoRef.value.paused) {
    await videoRef.value.play();
  } else {
    videoRef.value.pause();
  }
};

const toggleFullscreen = async () => {
  const fullscreenTarget = playerRoot.value?.closest(".live-stream-card") || playerRoot.value;
  if (!fullscreenTarget) return;

  if (document.fullscreenElement) {
    await document.exitFullscreen();
  } else {
    await fullscreenTarget.requestFullscreen();
  }
};

const togglePictureInPicture = async () => {
  if (!videoRef.value || !document.pictureInPictureEnabled) return;

  if (document.pictureInPictureElement) {
    await document.exitPictureInPicture();
  } else if (videoRef.value.readyState >= 2) {
    await videoRef.value.requestPictureInPicture();
  }
};

onMounted(() => {
  pipSupported.value = Boolean(props.protocol !== "HLS" && document.pictureInPictureEnabled && videoRef.value?.requestPictureInPicture);
  videoRef.value?.addEventListener("playing", markPlaying);
  videoRef.value?.addEventListener("pause", markPaused);
  document.addEventListener("fullscreenchange", updateFullscreenState);
  start();
});

onBeforeUnmount(() => {
  videoRef.value?.removeEventListener("playing", markPlaying);
  videoRef.value?.removeEventListener("pause", markPaused);
  document.removeEventListener("fullscreenchange", updateFullscreenState);
  peerConnection?.close();
  disposeHls();
});
</script>

<template>
  <div ref="playerRoot" class="stream-player">
    <video
      ref="videoRef"
      class="stream-player-video"
      autoplay
      muted
      playsinline
      :title="`${protocol} 실시간 영상`"
    />

    <div v-if="state === 'loading'" class="stream-loading">
      스트림을 불러오는 중입니다...
    </div>
    <div v-else-if="state === 'error'" class="stream-loading stream-error">
      스트림 연결에 실패했습니다.
      <button type="button" @click="start">다시 연결</button>
    </div>

    <span class="live-badge"><i /> LIVE</span>

    <div class="stream-controls">
      <button v-if="protocol !== 'HLS'" type="button" :aria-label="isPlaying ? '일시정지' : '재생'" @click="togglePlay">
        <Pause v-if="isPlaying" :size="14" />
        <Play v-else :size="14" />
      </button>
      <button
        type="button"
        :aria-label="isFullscreen ? '전체화면 닫기' : '전체화면'"
        @click="toggleFullscreen"
      >
        <Minimize2 v-if="isFullscreen" :size="14" />
        <Maximize2 v-else :size="14" />
      </button>
      <button
        v-if="protocol !== 'HLS' && pipSupported"
        type="button"
        aria-label="Picture-in-Picture"
        @click="togglePictureInPicture"
      >
        <PictureInPicture2 :size="14" />
      </button>
      <button type="button" aria-label="카메라 정보" @click.stop="emit('info')">
        <Info :size="14" />
      </button>
    </div>
  </div>
</template>
