<script setup>
import { reactive } from "vue";
import { useRouter } from "vue-router";
const router = useRouter();
const settings = reactive({ name: "김민준", phone: "010-1000-2026", candidateAlert: true, cctvAlert: true, statusAlert: true, browserAlert: true, soundAlert: false, sidebarDefault: "expanded", pageSize: 10, videoGrid: 4 });
const settingLinks = [
  { path: "/admin/cameras", title: "CCTV 관리", description: "CCTV 위치와 연결 상태를 관리합니다." },
  { path: "/admin/users", title: "사용자 관리", description: "관리자 계정과 권한을 관리합니다." },
  { path: "/admin/logs", title: "시스템 로그", description: "운영 기록과 감사 로그를 확인합니다." },
  { path: "/admin/notifications", title: "알림", description: "알림 내역과 상태를 확인합니다." }
];
</script>
<template>
  <section class="content-panel form-page wide-form-page"><div class="section-heading"><div><h2>설정</h2><p>프로필, 알림, 화면 기본값을 관리합니다.</p></div></div><section class="settings-shortcuts"><h3>관리 메뉴 바로가기</h3><div class="settings-shortcut-grid"><button v-for="link in settingLinks" :key="link.path" class="settings-shortcut" @click="router.push(link.path)"><strong>{{ link.title }}</strong><span>{{ link.description }}</span><small>바로가기 →</small></button></div></section><div class="form-grid settings-grid"><section><h3>프로필</h3><label>이름<input v-model="settings.name" /></label><label>연락처<input v-model="settings.phone" /></label><button class="ghost-button">비밀번호 변경</button></section><section><h3>알림 설정</h3><label class="check-row"><input v-model="settings.candidateAlert" type="checkbox" /> 후보 탐지 알림</label><label class="check-row"><input v-model="settings.cctvAlert" type="checkbox" /> CCTV 연결 알림</label><label class="check-row"><input v-model="settings.statusAlert" type="checkbox" /> 사건 상태 변경 알림</label><label class="check-row"><input v-model="settings.browserAlert" type="checkbox" /> 브라우저 알림</label><label class="check-row"><input v-model="settings.soundAlert" type="checkbox" /> 소리 알림</label></section><section><h3>화면 설정</h3><label>사이드바 기본 상태<select v-model="settings.sidebarDefault"><option value="expanded">펼침</option><option value="collapsed">접힘</option></select></label><label>페이지당 목록 개수<input v-model="settings.pageSize" type="number" /></label><label>영상 기본 분할 수<select v-model="settings.videoGrid"><option>1</option><option>4</option><option>9</option></select></label></section></div><div class="form-actions"><button class="primary-button">저장</button></div></section>
</template>
