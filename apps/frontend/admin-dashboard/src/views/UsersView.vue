<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { createAdmin, listAdmins, updateAdminStatus } from "../api/adminApi";
import BasePagination from "../components/common/BasePagination.vue";
import ConfirmModal from "../components/common/ConfirmModal.vue";
import StateBlock from "../components/common/StateBlock.vue";
import { useAuthStore } from "../stores/auth";

const LOGIN_ID_PATTERN = /^[a-z0-9._-]{4,50}$/;
const PAGE_SIZE = 10;

const auth = useAuthStore();
const admins = ref([]);
const page = ref(1);
const loading = ref(true);
const listError = ref("");
let listRequestId = 0;

const createModalOpen = ref(false);
const creating = ref(false);
const createError = ref("");
const createForm = reactive({
  loginId: "",
  name: "",
  password: "",
  passwordConfirm: ""
});
const fieldErrors = reactive({
  loginId: "",
  name: "",
  password: "",
  passwordConfirm: ""
});

const statusTarget = ref(null);
const statusEnabled = ref(false);
const statusPending = ref(false);
const statusError = ref("");

const totalPages = computed(() => Math.max(1, Math.ceil(admins.value.length / PAGE_SIZE)));
const visibleAdmins = computed(() => admins.value.slice(
  (page.value - 1) * PAGE_SIZE,
  page.value * PAGE_SIZE
));
const statusModalOpen = computed(() => Boolean(statusTarget.value));
const statusModalTitle = computed(() => statusEnabled.value ? "관리자 계정을 활성화할까요?" : "관리자 계정을 비활성화할까요?");
const statusModalMessage = computed(() => {
  const name = statusTarget.value?.name || statusTarget.value?.loginId || "선택한 관리자";
  return statusEnabled.value
    ? `${name} 계정이 다시 로그인하고 관리자 기능을 사용할 수 있습니다.`
    : `${name} 계정의 기존 세션이 종료되고 더 이상 로그인할 수 없습니다.`;
});

watch(totalPages, (nextTotalPages) => {
  if (page.value > nextTotalPages) page.value = nextTotalPages;
});

const apiErrorMessage = (cause, fallback) => {
  if (cause?.code === "ADMIN_LOGIN_ID_CONFLICT") return "이미 사용 중인 로그인 아이디입니다.";
  if (cause?.code === "ADMIN_NOT_FOUND") return "관리자 계정을 찾을 수 없습니다. 목록을 새로고침해 주세요.";
  if (cause?.status === 403) return "최고 관리자만 관리자 계정을 관리할 수 있습니다.";
  return cause?.message || fallback;
};

const load = async () => {
  const requestId = ++listRequestId;
  loading.value = true;
  listError.value = "";

  try {
    const result = await listAdmins();
    if (requestId !== listRequestId) return;
    if (!Array.isArray(result)) {
      throw new Error("관리자 계정 목록 응답 형식이 올바르지 않습니다.");
    }
    admins.value = result;
  } catch (cause) {
    if (requestId !== listRequestId) return;
    admins.value = [];
    listError.value = apiErrorMessage(cause, "관리자 계정 목록을 불러오지 못했습니다.");
  } finally {
    if (requestId === listRequestId) loading.value = false;
  }
};

const clearCreateForm = () => {
  Object.assign(createForm, { loginId: "", name: "", password: "", passwordConfirm: "" });
  Object.assign(fieldErrors, { loginId: "", name: "", password: "", passwordConfirm: "" });
  createError.value = "";
};

const openCreateModal = () => {
  clearCreateForm();
  createModalOpen.value = true;
};

const closeCreateModal = () => {
  if (creating.value) return;
  createModalOpen.value = false;
  clearCreateForm();
};

const validateCreateForm = () => {
  const loginId = createForm.loginId.trim().toLowerCase();
  const name = createForm.name.trim();
  const passwordBytes = new TextEncoder().encode(createForm.password).length;
  Object.assign(fieldErrors, { loginId: "", name: "", password: "", passwordConfirm: "" });

  if (!LOGIN_ID_PATTERN.test(loginId)) {
    fieldErrors.loginId = "로그인 아이디는 영문 소문자, 숫자, ., _, -만 사용해 4~50자로 입력해 주세요.";
  }
  if (!name) fieldErrors.name = "이름을 입력해 주세요.";
  else if (name.length > 50) fieldErrors.name = "이름은 50자 이하로 입력해 주세요.";

  if (createForm.password.length < 12 || createForm.password.length > 64 || passwordBytes > 72) {
    fieldErrors.password = "비밀번호는 12~64자이며 UTF-8 기준 72바이트 이하여야 합니다.";
  }
  if (createForm.password !== createForm.passwordConfirm) {
    fieldErrors.passwordConfirm = "비밀번호가 일치하지 않습니다.";
  }

  return {
    valid: !Object.values(fieldErrors).some(Boolean),
    payload: { loginId, name, password: createForm.password }
  };
};

const submitCreate = async () => {
  if (creating.value) return;
  createError.value = "";
  const { valid, payload } = validateCreateForm();
  if (!valid) return;

  creating.value = true;
  try {
    const created = await createAdmin(payload);
    admins.value = [created, ...admins.value.filter((admin) => admin.id !== created.id)];
    page.value = 1;
    createModalOpen.value = false;
    clearCreateForm();
  } catch (cause) {
    const message = apiErrorMessage(cause, "관리자 계정을 생성하지 못했습니다.");
    if (cause?.code === "ADMIN_LOGIN_ID_CONFLICT") fieldErrors.loginId = message;
    else createError.value = message;
  } finally {
    creating.value = false;
  }
};

const isCurrentAdmin = (admin) => String(admin.id) === String(auth.user?.id);

const requestStatusChange = (admin) => {
  if (isCurrentAdmin(admin)) return;
  statusTarget.value = admin;
  statusEnabled.value = !admin.enabled;
  statusError.value = "";
};

const closeStatusModal = () => {
  if (statusPending.value) return;
  statusTarget.value = null;
  statusError.value = "";
};

const confirmStatusChange = async () => {
  if (!statusTarget.value || statusPending.value) return;
  const target = statusTarget.value;
  const enabled = statusEnabled.value;
  statusPending.value = true;
  statusError.value = "";

  try {
    const updated = await updateAdminStatus(target.id, enabled);
    admins.value = admins.value.map((admin) => admin.id === target.id ? updated : admin);
    statusTarget.value = null;
  } catch (cause) {
    statusError.value = apiErrorMessage(cause, "관리자 계정 상태를 변경하지 못했습니다.");
  } finally {
    statusPending.value = false;
  }
};

const roleLabel = (role) => role === "SUPER_ADMIN" ? "최고 관리자" : "관리자";
const formatCreatedAt = (value) => {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Seoul"
  }).format(date);
};

onMounted(load);
onBeforeUnmount(() => { listRequestId += 1; });
</script>

<template>
  <section class="content-panel">
    <div class="section-heading">
      <div>
        <h2>관리자 계정 관리</h2>
        <p>관리자 계정을 생성하고 로그인 가능 상태를 관리합니다.</p>
      </div>
      <button class="primary-button" type="button" :disabled="loading" @click="openCreateModal">관리자 계정 생성</button>
    </div>

    <StateBlock :loading="loading" :error="listError" :empty="admins.length === 0" @retry="load">
      <div class="table-scroll">
        <table class="case-table admin-account-table">
          <thead>
            <tr>
              <th>이름</th>
              <th>로그인 아이디</th>
              <th>역할</th>
              <th>상태</th>
              <th>생성일</th>
              <th>작업</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="admin in visibleAdmins" :key="admin.id">
              <td>{{ admin.name }}</td>
              <td class="mono">{{ admin.loginId }}</td>
              <td><span :class="['admin-role-badge', admin.role === 'SUPER_ADMIN' && 'super']">{{ roleLabel(admin.role) }}</span></td>
              <td><span :class="['status-badge', admin.enabled ? 'green' : 'gray']">{{ admin.enabled ? "활성" : "비활성" }}</span></td>
              <td>{{ formatCreatedAt(admin.createdAt) }}</td>
              <td>
                <button
                  class="ghost-button admin-status-button"
                  type="button"
                  :disabled="isCurrentAdmin(admin)"
                  :title="isCurrentAdmin(admin) ? '현재 로그인한 계정의 상태는 변경할 수 없습니다.' : undefined"
                  @click="requestStatusChange(admin)"
                >
                  {{ admin.enabled ? "비활성화" : "활성화" }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <BasePagination v-model:page="page" :total-pages="totalPages" :total-count="admins.length" />
    </StateBlock>

    <div v-if="createModalOpen" class="modal-backdrop" @click.self="closeCreateModal">
      <section class="modal admin-create-modal" role="dialog" aria-modal="true" aria-labelledby="admin-create-title">
        <h3 id="admin-create-title">관리자 계정 생성</h3>
        <p>새 계정은 일반 관리자 권한과 활성 상태로 생성됩니다.</p>
        <form class="admin-create-form" @submit.prevent="submitCreate">
          <label>
            <span>로그인 아이디</span>
            <input
              v-model="createForm.loginId"
              autocomplete="off"
              maxlength="50"
              placeholder="admin.operator"
              :disabled="creating"
              :aria-invalid="Boolean(fieldErrors.loginId)"
              @input="createError = ''; fieldErrors.loginId = ''"
            />
            <small>{{ fieldErrors.loginId }}</small>
          </label>
          <label>
            <span>이름</span>
            <input v-model="createForm.name" autocomplete="off" maxlength="50" placeholder="관리자 이름" :disabled="creating" :aria-invalid="Boolean(fieldErrors.name)" @input="fieldErrors.name = ''" />
            <small>{{ fieldErrors.name }}</small>
          </label>
          <label>
            <span>초기 비밀번호</span>
            <input v-model="createForm.password" type="password" autocomplete="new-password" maxlength="64" placeholder="12~64자" :disabled="creating" :aria-invalid="Boolean(fieldErrors.password)" @input="fieldErrors.password = ''" />
            <small>{{ fieldErrors.password }}</small>
          </label>
          <label>
            <span>비밀번호 확인</span>
            <input v-model="createForm.passwordConfirm" type="password" autocomplete="new-password" maxlength="64" placeholder="비밀번호 다시 입력" :disabled="creating" :aria-invalid="Boolean(fieldErrors.passwordConfirm)" @input="fieldErrors.passwordConfirm = ''" />
            <small>{{ fieldErrors.passwordConfirm }}</small>
          </label>
          <p v-if="createError" class="form-error" role="alert">{{ createError }}</p>
          <div class="modal-actions">
            <button class="ghost-button" type="button" :disabled="creating" @click="closeCreateModal">취소</button>
            <button class="primary-button" type="submit" :disabled="creating">{{ creating ? "생성 중" : "계정 생성" }}</button>
          </div>
        </form>
      </section>
    </div>

    <ConfirmModal
      :open="statusModalOpen"
      :title="statusModalTitle"
      :message="statusModalMessage"
      :confirm-text="statusEnabled ? '활성화' : '비활성화'"
      :loading="statusPending"
      :error="statusError"
      @close="closeStatusModal"
      @confirm="confirmStatusChange"
    />
  </section>
</template>
