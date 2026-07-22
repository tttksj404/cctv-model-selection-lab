<script setup>
import { onMounted, ref } from "vue";
import { getAuditLogs } from "../api/mockApi";
const logs = ref([]); const selected = ref(null); onMounted(async () => logs.value = await getAuditLogs());
</script>
<template>
  <section class="content-panel"><div class="section-heading"><div><h2>시스템 로그</h2><p>로그 상세는 모달로 확인합니다.</p></div></div><div class="filter-bar"><label>로그 종류<select><option>전체</option><option>로그인</option><option>사건 상태 변경</option><option>후보 판정</option><option>시스템 오류</option></select></label><label>사용자<input /></label><label>기간<input /></label><button class="reset-button">조회</button></div><div class="table-scroll"><table class="case-table"><thead><tr><th>발생 시각</th><th>사용자</th><th>작업 유형</th><th>대상</th><th>결과</th><th>IP</th><th></th></tr></thead><tbody><tr v-for="log in logs" :key="log.id"><td>{{ log.time }}</td><td>{{ log.actor }}</td><td>{{ log.type }}</td><td>{{ log.target }}</td><td>{{ log.result }}</td><td>{{ log.ip }}</td><td><button class="ghost-button" @click="selected=log">상세보기</button></td></tr></tbody></table></div><div v-if="selected" class="modal-backdrop" @click.self="selected=null"><section class="modal"><h3>로그 상세</h3><p>{{ selected.detail }}</p><button class="primary-button" @click="selected=null">확인</button></section></div></section>
</template>
