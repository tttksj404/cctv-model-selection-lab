<script setup>
import { reactive } from "vue";
import { useRouter } from "vue-router";
const router = useRouter(); const form = reactive({ name: "", address: "", detail: "", lat: "", lng: "", zone: "", streamUrl: "", desc: "", active: true });
</script>
<template>
  <section class="content-panel form-page"><div class="section-heading"><div><h2>CCTV 등록·수정</h2><p>지도 클릭 좌표 선택과 연결 테스트를 고려한 입력 화면입니다.</p></div></div><div class="form-grid"><section><h3>기본 정보</h3><label>CCTV 이름<input v-model="form.name" /></label><label>설치 위치<input v-model="form.address" /></label><label>상세 주소<input v-model="form.detail" /></label><label>구역<input v-model="form.zone" /></label></section><section><h3>좌표 및 연결</h3><label>위도<input v-model="form.lat" /></label><label>경도<input v-model="form.lng" /></label><label>스트림 URL<input v-model="form.streamUrl" placeholder="민감 정보는 마스킹 예정" /></label><label>장비 설명<textarea v-model="form.desc" /></label><label class="check-row"><input v-model="form.active" type="checkbox" /> 사용</label><button class="ghost-button">스트림 연결 테스트</button></section><section class="wide"><div class="map-panel">지도 클릭으로 좌표 선택</div></section></div><div class="form-actions"><button class="ghost-button" @click="router.back()">취소</button><button class="primary-button" @click="router.push('/admin/cameras')">저장</button></div></section>
</template>
