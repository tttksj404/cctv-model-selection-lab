<script setup>
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";

const router = useRouter();
const verified = ref(false);
const adminNumber = ref("");
const verifyError = ref("");
const saved = ref(false);
const profile = reactive({ name: "김민준", email: "admin@eyesforu.local", phone: "010-1000-2026", role: "관제 운영자" });
const verifyAdmin = () => {
  if (!adminNumber.value.trim()) { verifyError.value = "관리자 번호를 입력해 주세요."; return; }
  verifyError.value = "";
  verified.value = true;
};
const save = () => { saved.value = true; window.setTimeout(() => { saved.value = false; }, 1800); };
</script>

<template>
  <section v-if="verified" class="content-panel form-page profile-page">
    <div class="section-heading"><div><h2>프로필 관리</h2><p>관제 운영자 계정 정보와 보안 설정을 관리합니다.</p></div></div>
    <div class="profile-security-note"><strong>보안 안내</strong><span>중요한 계정 정보 변경은 감사 로그에 기록됩니다.</span></div>
    <div class="profile-form-grid">
      <section><h3>기본 정보</h3><label>이름<input v-model="profile.name" /></label><label>이메일<input v-model="profile.email" type="email" disabled /></label><label>연락처<input v-model="profile.phone" /></label><label>권한<input v-model="profile.role" disabled /></label></section>
      <section><h3>보안</h3><p class="profile-help">비밀번호 변경은 별도 절차를 통해 처리됩니다.</p><button class="ghost-button">비밀번호 변경</button></section>
    </div>
    <div class="form-actions"><button class="ghost-button" @click="router.push('/admin/settings')">취소</button><button class="primary-button" @click="save">저장</button><span v-if="saved" class="draft-saved">저장됨</span></div>
  </section>
  <div v-else class="modal-backdrop profile-auth-backdrop">
    <section class="modal profile-auth-modal">
      <h3>관리자 확인</h3>
      <p>프로필 관리 페이지에 들어가려면 관리자 번호를 입력해 주세요.</p>
      <label>관리자 번호<input v-model="adminNumber" placeholder="관리자 번호 입력" @keyup.enter="verifyAdmin" /></label>
      <small v-if="verifyError" class="form-error">{{ verifyError }}</small>
      <div class="modal-actions"><button class="ghost-button" @click="router.push('/admin/settings')">취소</button><button class="primary-button" @click="verifyAdmin">확인</button></div>
    </section>
  </div>
</template>
