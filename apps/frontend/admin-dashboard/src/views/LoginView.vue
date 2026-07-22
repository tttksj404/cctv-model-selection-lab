<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const router = useRouter();
const auth = useAuthStore();
const email = ref("admin@eyesforu.local");
const password = ref("admin1234");
const showPassword = ref(false);
const error = ref("");
const loading = ref(false);

const submit = async () => {
  error.value = "";
  loading.value = true;
  try {
    await auth.login({ email: email.value, password: password.value });
    router.push("/admin/dashboard");
  } catch (err) {
    error.value = err.message;
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <main class="login-page">
    <form class="login-card" @submit.prevent="submit">
      <div class="brand-mark"><img src="/logo.png" alt="Eyes On U" /></div>
      <h1>관리자 로그인</h1>
      <p>CCTV 실종자 탐색 관제 서비스</p>
      <label>아이디<input v-model="email" required /></label>
      <label>비밀번호<input v-model="password" :type="showPassword ? 'text' : 'password'" required /></label>
      <label class="check-row"><input v-model="showPassword" type="checkbox" /> 비밀번호 표시</label>
      <div v-if="error" class="form-error">{{ error }}</div>
      <button class="primary-button" :disabled="loading">{{ loading ? "로그인 중" : "로그인" }}</button>
    </form>
  </main>
</template>
