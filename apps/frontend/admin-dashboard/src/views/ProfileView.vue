<script setup>
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const router = useRouter();
const auth = useAuthStore();

const profile = ref(null);
const loading = ref(true);
const loadError = ref("");

const originalName = ref("");
const nameForm = reactive({ name: "" });
const nameError = ref("");
const nameRequestError = ref("");
const nameSuccess = ref("");
const savingName = ref(false);

const passwordForm = reactive({
  currentPassword: "",
  newPassword: "",
  passwordConfirm: ""
});
const passwordErrors = reactive({
  currentPassword: "",
  newPassword: "",
  passwordConfirm: ""
});
const passwordRequestError = ref("");
const passwordSuccess = ref("");
const savingPassword = ref(false);

const errorMessage = (cause, fallback) => cause?.message || fallback;

const applyProfile = (admin) => {
  profile.value = admin;
  originalName.value = admin.name || "";
  nameForm.name = originalName.value;
};

const loadProfile = async () => {
  loading.value = true;
  loadError.value = "";

  try {
    const admin = await auth.refreshCurrentAdmin();
    if (!admin || typeof admin !== "object") {
      throw new Error("관리자 프로필 응답 형식이 올바르지 않습니다.");
    }
    applyProfile(admin);
  } catch (cause) {
    profile.value = null;
    loadError.value = errorMessage(cause, "프로필 정보를 불러오지 못했습니다.");
  } finally {
    loading.value = false;
  }
};

const clearNameFeedback = () => {
  nameError.value = "";
  nameRequestError.value = "";
  nameSuccess.value = "";
};

const validateName = () => {
  const name = nameForm.name.trim();
  nameError.value = "";

  if (!name) nameError.value = "이름을 입력해 주세요.";
  else if (name.length > 50) nameError.value = "이름은 50자 이하로 입력해 주세요.";
  else if (name === originalName.value) nameError.value = "변경된 이름이 없습니다.";

  return { valid: !nameError.value, name };
};

const submitName = async () => {
  if (savingName.value) return;
  nameRequestError.value = "";
  nameSuccess.value = "";
  const { valid, name } = validateName();
  if (!valid) return;

  savingName.value = true;
  try {
    const result = await auth.updateCurrentAdmin({ name });
    const updatedAdmin = result?.admin || { ...profile.value, name };
    applyProfile(updatedAdmin);
    nameSuccess.value = "이름이 변경되었습니다.";
  } catch (cause) {
    nameRequestError.value = errorMessage(cause, "이름을 변경하지 못했습니다.");
  } finally {
    savingName.value = false;
  }
};

const clearPasswordFieldError = (field) => {
  passwordErrors[field] = "";
  passwordRequestError.value = "";
  passwordSuccess.value = "";
};

const validatePassword = () => {
  Object.assign(passwordErrors, {
    currentPassword: "",
    newPassword: "",
    passwordConfirm: ""
  });

  if (!passwordForm.currentPassword) {
    passwordErrors.currentPassword = "현재 비밀번호를 입력해 주세요.";
  }

  const newPasswordBytes = new TextEncoder().encode(passwordForm.newPassword).length;
  if (
    passwordForm.newPassword.length < 12
      || passwordForm.newPassword.length > 64
      || newPasswordBytes > 72
  ) {
    passwordErrors.newPassword = "새 비밀번호는 12~64자이며 UTF-8 기준 72바이트 이하여야 합니다.";
  }

  if (passwordForm.newPassword !== passwordForm.passwordConfirm) {
    passwordErrors.passwordConfirm = "새 비밀번호가 일치하지 않습니다.";
  }

  return !Object.values(passwordErrors).some(Boolean);
};

const clearPasswordForm = () => {
  Object.assign(passwordForm, {
    currentPassword: "",
    newPassword: "",
    passwordConfirm: ""
  });
};

const submitPassword = async () => {
  if (savingPassword.value) return;
  passwordRequestError.value = "";
  passwordSuccess.value = "";
  if (!validatePassword()) return;

  savingPassword.value = true;
  try {
    const result = await auth.updateCurrentAdmin({
      currentPassword: passwordForm.currentPassword,
      newPassword: passwordForm.newPassword
    });

    if (result?.reauthenticationRequired) {
      await router.replace("/login?reason=password-changed&redirect=/admin/profile");
      return;
    }

    if (result?.admin) profile.value = result.admin;
    clearPasswordForm();
    passwordSuccess.value = "비밀번호가 변경되었습니다.";
  } catch (cause) {
    if (cause?.code === "CURRENT_PASSWORD_MISMATCH") {
      passwordErrors.currentPassword = cause.message || "현재 비밀번호가 올바르지 않습니다.";
    } else {
      passwordRequestError.value = errorMessage(cause, "비밀번호를 변경하지 못했습니다.");
    }
  } finally {
    savingPassword.value = false;
  }
};

onMounted(loadProfile);
</script>

<template>
  <section class="content-panel form-page profile-page">
    <div class="section-heading">
      <div>
        <h2>프로필 관리</h2>
        <p>현재 관리자 계정 정보와 비밀번호를 안전하게 관리합니다.</p>
      </div>
    </div>

    <div v-if="loading" class="state-view profile-state">
      <strong>프로필 정보를 불러오는 중입니다.</strong>
    </div>

    <div v-else-if="loadError" class="state-view error profile-state" role="alert">
      <strong>{{ loadError }}</strong>
      <button class="ghost-button" type="button" @click="loadProfile">다시 시도</button>
    </div>

    <template v-else-if="profile">
      <div class="profile-security-note">
        <strong>보안 안내</strong>
        <span>이름과 비밀번호 변경은 감사 로그에 기록됩니다.</span>
      </div>

      <section class="profile-section profile-readonly-section" aria-labelledby="profile-account-title">
        <div class="profile-section-heading">
          <h3 id="profile-account-title">계정 정보</h3>
          <p>계정 식별 정보와 권한은 이 화면에서 변경할 수 없습니다.</p>
        </div>
        <div class="profile-readonly-grid">
          <label>
            <span>관리자 ID</span>
            <input name="profileId" :value="profile.id" readonly />
          </label>
          <label>
            <span>로그인 아이디</span>
            <input name="loginId" :value="profile.loginId" readonly />
          </label>
          <label>
            <span>권한</span>
            <input name="role" :value="profile.role" readonly />
          </label>
        </div>
      </section>

      <div class="profile-form-grid">
        <section class="profile-section" aria-labelledby="profile-name-title">
          <div class="profile-section-heading">
            <h3 id="profile-name-title">이름 변경</h3>
            <p>관리 화면에 표시할 이름을 변경합니다.</p>
          </div>
          <form class="profile-name-form" @submit.prevent="submitName">
            <label>
              <span>이름</span>
              <input
                v-model="nameForm.name"
                name="name"
                autocomplete="name"
                maxlength="50"
                :disabled="savingName"
                :aria-invalid="Boolean(nameError)"
                @input="clearNameFeedback"
              />
              <small>{{ nameError }}</small>
            </label>
            <p v-if="nameRequestError" class="form-error" role="alert">{{ nameRequestError }}</p>
            <p v-if="nameSuccess" class="form-success" role="status">{{ nameSuccess }}</p>
            <div class="profile-form-actions">
              <button class="primary-button" type="submit" :disabled="savingName">
                {{ savingName ? "저장 중" : "이름 저장" }}
              </button>
            </div>
          </form>
        </section>

        <section class="profile-section" aria-labelledby="profile-password-title">
          <div class="profile-section-heading">
            <h3 id="profile-password-title">비밀번호 변경</h3>
            <p>변경 후에는 새 비밀번호로 다시 로그인해야 합니다.</p>
          </div>
          <form class="profile-password-form" @submit.prevent="submitPassword">
            <label>
              <span>현재 비밀번호</span>
              <input
                v-model="passwordForm.currentPassword"
                name="currentPassword"
                type="password"
                autocomplete="current-password"
                maxlength="128"
                :disabled="savingPassword"
                :aria-invalid="Boolean(passwordErrors.currentPassword)"
                @input="clearPasswordFieldError('currentPassword')"
              />
              <small>{{ passwordErrors.currentPassword }}</small>
            </label>
            <label>
              <span>새 비밀번호</span>
              <input
                v-model="passwordForm.newPassword"
                name="newPassword"
                type="password"
                autocomplete="new-password"
                maxlength="64"
                placeholder="12~64자, UTF-8 72바이트 이하"
                :disabled="savingPassword"
                :aria-invalid="Boolean(passwordErrors.newPassword)"
                @input="clearPasswordFieldError('newPassword')"
              />
              <small>{{ passwordErrors.newPassword }}</small>
            </label>
            <label>
              <span>새 비밀번호 확인</span>
              <input
                v-model="passwordForm.passwordConfirm"
                name="passwordConfirm"
                type="password"
                autocomplete="new-password"
                maxlength="64"
                :disabled="savingPassword"
                :aria-invalid="Boolean(passwordErrors.passwordConfirm)"
                @input="clearPasswordFieldError('passwordConfirm')"
              />
              <small>{{ passwordErrors.passwordConfirm }}</small>
            </label>
            <p v-if="passwordRequestError" class="form-error" role="alert">{{ passwordRequestError }}</p>
            <p v-if="passwordSuccess" class="form-success" role="status">{{ passwordSuccess }}</p>
            <div class="profile-form-actions">
              <button class="primary-button" type="submit" :disabled="savingPassword">
                {{ savingPassword ? "변경 중" : "비밀번호 변경" }}
              </button>
            </div>
          </form>
        </section>
      </div>
    </template>
  </section>
</template>
