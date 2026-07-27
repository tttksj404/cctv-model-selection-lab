<script setup>
import { computed, onMounted, ref } from "vue";
import { getUsers } from "../api/mockApi";
import BasePagination from "../components/common/BasePagination.vue";
const users = ref([]); const roleTarget = ref(null); const pendingRole = ref(""); const roleModalOpen = ref(false); const page = ref(1); const pageSize = 10;
const totalPages = computed(() => Math.max(1, Math.ceil(users.value.length / pageSize)));
const visibleUsers = computed(() => users.value.slice((page.value - 1) * pageSize, page.value * pageSize));
onMounted(async () => users.value = await getUsers());
const requestRoleChange = (user, role) => {
  if (role === "시스템 관리자") { roleTarget.value = user; pendingRole.value = role; roleModalOpen.value = true; return; }
  user.role = role;
};
const confirmRoleChange = () => { if (roleTarget.value) roleTarget.value.role = pendingRole.value; roleTarget.value = null; pendingRole.value = ""; roleModalOpen.value = false; };
const cancelRoleChange = () => { roleTarget.value = null; pendingRole.value = ""; roleModalOpen.value = false; };
</script>
<template>
  <section class="content-panel"><div class="section-heading"><div><h2>사용자 관리</h2><p>역할별 접근 메뉴를 분리할 수 있는 권한 구조입니다.</p></div><button class="primary-button">사용자 등록</button></div><div class="table-scroll"><table class="case-table user-table"><thead><tr><th>이름</th><th>아이디</th><th>역할</th><th>연락처</th><th>상태</th><th>최근 로그인</th><th>권한 설정</th></tr></thead><tbody><tr v-for="u in visibleUsers" :key="u.id"><td>{{ u.name }}</td><td>{{ u.email }}</td><td>{{ u.role }}</td><td>{{ u.phone }}</td><td>{{ u.status }}</td><td>{{ u.lastLogin }}</td><td><select :value="u.role" class="user-role-select" @change="requestRoleChange(u, $event.target.value)"><option>시스템 관리자</option><option>관제 관리자</option><option>일반 관제자</option></select></td></tr></tbody></table></div><BasePagination v-model:page="page" :total-pages="totalPages" :total-count="users.length" /><div v-if="roleModalOpen" class="modal-backdrop" @click.self="cancelRoleChange"><section class="modal role-warning-modal"><h3>시스템 관리자 권한을 부여할까요?</h3><p>전체 시스템 설정과 사용자 권한을 변경할 수 있는 최고 권한입니다. 신중하게 부여해 주세요.</p><div class="modal-actions"><button class="ghost-button" @click="cancelRoleChange">취소</button><button class="primary-button" @click="confirmRoleChange">권한 부여</button></div></section></div></section>
</template>
