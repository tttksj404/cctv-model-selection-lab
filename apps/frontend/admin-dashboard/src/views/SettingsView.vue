<script setup>
import { computed } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const router = useRouter();
const auth = useAuthStore();
const allSettingLinks = [
  { path: "/admin/cameras", title: "CCTV 관리", description: "CCTV 위치와 연결 상태를 관리합니다." },
  { path: "/admin/users", title: "관리자 계정 관리", description: "관리자 계정의 생성과 활성 상태를 관리합니다.", requiresSuperAdmin: true },
  { path: "/admin/logs", title: "시스템 로그", description: "운영 기록과 감사 로그를 확인합니다." },
  { path: "/admin/notifications", title: "알림", description: "알림 내역과 수신 설정을 관리합니다." }
];
const settingLinks = computed(() => allSettingLinks.filter((link) =>
  !link.requiresSuperAdmin || auth.isSuperAdmin));
</script>

<template>
  <section class="content-panel form-page wide-form-page">
    <div class="section-heading">
      <div><h2>설정</h2><p>관제 시스템 운영 설정과 관리 메뉴를 확인합니다.</p></div>
    </div>

    <section class="settings-profile-summary">
      <div><h3>프로필 관리</h3><p>개인정보와 보안 정보는 별도 관리 화면에서 수정할 수 있습니다.</p></div>
      <button class="ghost-button" @click="router.push('/admin/profile')">프로필 관리</button>
    </section>

    <section class="settings-shortcuts">
      <h3>관리 메뉴 바로가기</h3>
      <div class="settings-shortcut-grid">
        <button v-for="link in settingLinks" :key="link.path" class="settings-shortcut" @click="router.push(link.path)">
          <strong>{{ link.title }}</strong><span>{{ link.description }}</span><small>바로가기 →</small>
        </button>
      </div>
    </section>

  </section>
</template>
