<script setup>
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const loginId = ref("");
const password = ref("");
const showPassword = ref(false);
const initialReason = Array.isArray(route.query.reason) ? route.query.reason[0] : route.query.reason;
const initialError = {
  "server-unavailable": "서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.",
  "session-expired": "로그인 세션이 만료되었습니다. 다시 로그인해 주세요.",
  "authentication-required": "인증이 필요합니다. 다시 로그인해 주세요."
}[initialReason] || "";
const error = ref(initialError);
const loading = ref(false);

const safeRedirect = () => {
  const value = Array.isArray(route.query.redirect) ? route.query.redirect[0] : route.query.redirect;
  if (typeof value !== "string") return "/admin/dashboard";
  return value === "/admin" || value.startsWith("/admin/") ? value : "/admin/dashboard";
};

const submit = async () => {
  if (loading.value) return;
  error.value = "";
  loading.value = true;
  try {
    await auth.login({ loginId: loginId.value, password: password.value });
    await router.replace(safeRedirect());
  } catch (err) {
    error.value = err?.message || "로그인 중 오류가 발생했습니다.";
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <main class="login-page">
    <form class="login-card" autocomplete="off" @submit.prevent="submit">
      <div class="brand-mark"><img src="/logo.png" alt="Eyes On U" /></div>
      <h1>관리자 로그인</h1>
      <p>CCTV 실종자 탐색 관제 서비스</p>
      <label>아이디<input v-model="loginId" autocomplete="off" required /></label>
      <label>비밀번호<input v-model="password" autocomplete="off" :type="showPassword ? 'text' : 'password'" required /></label>
      <label class="check-row"><input v-model="showPassword" type="checkbox" /> 비밀번호 표시</label>
      <div v-if="error" class="form-error">{{ error }}</div>
      <button class="primary-button" :disabled="loading">{{ loading ? "로그인 중" : "로그인" }}</button>
    </form>
  </main>
</template>
