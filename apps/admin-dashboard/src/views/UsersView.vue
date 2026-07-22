<script setup>
import { onMounted, ref } from "vue";
import { getUsers } from "../api/mockApi";
const users = ref([]); onMounted(async () => users.value = await getUsers());
</script>
<template>
  <section class="content-panel"><div class="section-heading"><div><h2>사용자 관리</h2><p>역할별 접근 메뉴를 분리할 수 있는 권한 구조입니다.</p></div><button class="primary-button">사용자 등록</button></div><div class="table-scroll"><table class="case-table"><thead><tr><th>이름</th><th>아이디</th><th>역할</th><th>연락처</th><th>상태</th><th>최근 로그인</th><th>기능</th></tr></thead><tbody><tr v-for="u in users" :key="u.id"><td>{{ u.name }}</td><td>{{ u.email }}</td><td>{{ u.role }}</td><td>{{ u.phone }}</td><td>{{ u.status }}</td><td>{{ u.lastLogin }}</td><td><button class="ghost-button">정보 수정</button><button class="ghost-button">비밀번호 초기화</button></td></tr></tbody></table></div></section>
</template>
