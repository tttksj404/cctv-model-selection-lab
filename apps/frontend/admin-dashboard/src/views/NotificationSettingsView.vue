<script setup>
import { reactive } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const settings = reactive({ candidateAlert: true, cctvAlert: true, statusAlert: true, browserAlert: true, soundAlert: false });
</script>

<template>
  <section class="content-panel notification-settings-page">
    <div class="section-heading"><div><h2>알림 설정</h2><p>관제 시스템에서 받을 알림의 종류와 방식을 설정합니다.</p></div><button class="ghost-button" @click="router.push('/admin/notifications')">뒤로가기</button></div>
    <section class="notification-settings-card">
      <div class="notification-setting-row"><div><strong>후보 탐지 알림</strong><span>새로운 후보가 탐지되면 알립니다.</span></div><button class="toggle-switch" :class="{ active: settings.candidateAlert }" type="button" role="switch" :aria-checked="settings.candidateAlert" @click="settings.candidateAlert = !settings.candidateAlert"><span></span></button></div>
      <div class="notification-setting-row"><div><strong>CCTV 연결 알림</strong><span>카메라 연결 상태가 변경되면 알립니다.</span></div><button class="toggle-switch" :class="{ active: settings.cctvAlert }" type="button" role="switch" :aria-checked="settings.cctvAlert" @click="settings.cctvAlert = !settings.cctvAlert"><span></span></button></div>
      <div class="notification-setting-row"><div><strong>사건 상태 변경 알림</strong><span>사건의 진행 상태가 변경되면 알립니다.</span></div><button class="toggle-switch" :class="{ active: settings.statusAlert }" type="button" role="switch" :aria-checked="settings.statusAlert" @click="settings.statusAlert = !settings.statusAlert"><span></span></button></div>
      <div class="notification-setting-row"><div><strong>브라우저 알림</strong><span>브라우저 알림 권한을 사용합니다.</span></div><button class="toggle-switch" :class="{ active: settings.browserAlert }" type="button" role="switch" :aria-checked="settings.browserAlert" @click="settings.browserAlert = !settings.browserAlert"><span></span></button></div>
      <div class="notification-setting-row"><div><strong>소리 알림</strong><span>중요 알림에 소리를 함께 사용합니다.</span></div><button class="toggle-switch" :class="{ active: settings.soundAlert }" type="button" role="switch" :aria-checked="settings.soundAlert" @click="settings.soundAlert = !settings.soundAlert"><span></span></button></div>
      <button class="primary-button notification-settings-save">알림 설정 저장</button>
    </section>
  </section>
</template>
