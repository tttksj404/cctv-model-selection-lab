<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
const router = useRouter(); const caseNumber = ref("CASE-2026-0417"); const code = ref("123456"); const error = ref("");
const lookup = () => { if (!caseNumber.value || !code.value) error.value = "사건번호와 인증번호를 입력해 주세요."; else router.push("/report/cases/mock-access-token"); };
</script>
<template>
  <main class="login-page"><section class="login-card report-card"><h1>신고자 사건 조회</h1><p>민감한 AI 판정 정보 없이 진행 상태만 안내합니다.</p><label>사건번호<input v-model="caseNumber" /></label><label>조회용 인증번호<input v-model="code" /></label><div v-if="error" class="form-error">{{ error }}</div><button class="primary-button" @click="lookup">조회</button></section></main>
</template>
