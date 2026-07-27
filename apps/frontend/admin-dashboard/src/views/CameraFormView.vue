<script setup>
import { computed, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { useRoute } from "vue-router";

const router = useRouter();
const route = useRoute();
const isEditMode = computed(() => Boolean(route.params.cameraId));
const streamTestOpen = ref(false);
const streamTesting = ref(false);
const streamConnected = ref(false);
const openStreamTest = () => {
  streamTestOpen.value = true;
  streamTesting.value = true;
  streamConnected.value = false;
  window.setTimeout(() => { streamTesting.value = false; streamConnected.value = true; }, 900);
};
const form = reactive({ name: "", address: "", detail: "", lat: "", lng: "", zone: "", streamUrl: "", desc: "", active: true });
</script>

<template>
  <section class="content-panel form-page wide-form-page">
    <div class="section-heading"><div><h2>{{ isEditMode ? "CCTV 수정" : "CCTV 등록" }}</h2><p>지도 클릭 좌표 선택과 연결 테스트를 고려한 입력 화면입니다.</p></div></div>
    <div class="form-grid">
      <section><h3>기본 정보</h3><label>CCTV 이름<input v-model="form.name" /></label><label>설치 위치<input v-model="form.address" /></label><label>상세 주소<input v-model="form.detail" /></label><label>구역<input v-model="form.zone" /></label></section>
      <section><h3>좌표 및 연결</h3><label>위도<input v-model="form.lat" /></label><label>경도<input v-model="form.lng" /></label><label>스트림 URL<input v-model="form.streamUrl" placeholder="민감 정보는 마스킹 예정" /></label><label>장비 설명<textarea v-model="form.desc" /></label><div class="camera-active-field"><label class="check-row"><input v-model="form.active" type="checkbox" /> 운영 여부</label><small>점검 중이거나 장애가 발생한 CCTV는 운영 대상에서 제외할 수 있습니다.</small></div><button class="ghost-button" @click="openStreamTest">스트림 연결 테스트</button></section>
      <section class="wide"><div class="map-panel">지도 클릭으로 좌표 선택</div></section>
    </div>
    <div class="form-actions"><button class="ghost-button" @click="router.back()">취소</button><button class="primary-button" @click="router.push('/admin/cameras')">저장</button></div>
    <div v-if="streamTestOpen" class="modal-backdrop" @click.self="streamTestOpen = false"><section class="modal stream-test-modal"><div class="section-heading"><div><h3>스트림 연결 테스트</h3><p>{{ streamTesting ? "CCTV 스트림 연결 상태를 확인하고 있습니다." : "연결 테스트 결과와 실시간 미리보기입니다." }}</p></div><button class="ghost-button" @click="streamTestOpen = false">닫기</button></div><div class="stream-preview"><span v-if="streamTesting">SIGNAL CHECKING...</span><span v-else>CCTV LIVE PREVIEW</span><small>{{ form.name || "CCTV 미등록" }}</small></div><div class="stream-signal"><div class="signal-bars"><i v-for="level in 4" :key="level" :class="{ active: !streamTesting && streamConnected && level <= 4 }" :style="{ height: `${level * 7}px` }" /></div><strong>{{ streamTesting ? "연결 확인 중" : streamConnected ? "연결 양호" : "연결 실패" }}</strong><span>{{ streamTesting ? "잠시만 기다려 주세요." : streamConnected ? "스트림 신호가 안정적으로 수신되고 있습니다." : "스트림 연결을 확인해 주세요." }}</span></div></section></div>
  </section>
</template>
