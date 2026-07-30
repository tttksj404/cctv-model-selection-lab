<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from "vue";
import { FolderOpen, MapPin } from "lucide-vue-next";
import { useRoute, useRouter } from "vue-router";
import {
  createCase,
  deleteCasePhoto,
  getCase,
  putCasePhoto,
  updateCase
} from "../api/caseApi";
import ConfirmModal from "../components/common/ConfirmModal.vue";
import {
  buildCaseUpdatePatch,
  buildCreateCasePayload,
  caseDetailToForm
} from "../domain/caseMapper";

const router = useRouter();
const route = useRoute();
const fileInput = ref(null);
const confirmOpen = ref(false);
const draftSaved = ref(false);
const errors = ref({});
const loading = ref(false);
const loadError = ref("");
const operationError = ref("");
const photoError = ref("");
const submitting = ref(false);
const deletingPhoto = ref(false);
const initialForm = ref(null);
const existingPhotoUrl = ref("");
const caseStatus = ref(null);
const pendingPhotoError = ref("");
let loadRequestId = 0;
let submitRequestId = 0;

const currentYear = new Date().getFullYear();
const createEmptyForm = () => ({
  reporterName: "",
  reporterPhone: "",
  relation: "",
  name: "",
  gender: "여",
  age: "",
  birthYear: "",
  photo: "",
  photoFile: null,
  head: "",
  face: "",
  top: "",
  bottom: "",
  shoes: "",
  accessory: "",
  body: "",
  feature: "",
  lastSeenDate: "",
  lastSeenTime: "",
  lastSeenLocation: "",
  story: "",
  prompt: "",
  exclude: "",
  searchFrom: "마지막 목격 시각",
  searchFromCustomDate: "",
  searchFromCustomTime: "",
  searchTo: "현재 시각",
  searchToCustomDate: "",
  searchToCustomTime: "",
  zones: "마지막 목격 위치 주변",
  zonesCustom: ""
});
const form = reactive(createEmptyForm());
const photoPreviewUrl = ref("");
let photoObjectUrl = "";

const isEditMode = computed(() => Boolean(route.params.caseId));
const isClosed = computed(() => caseStatus.value === "CLOSED");
const photoDisplayUrl = computed(() => photoPreviewUrl.value || existingPhotoUrl.value);
const pageTitle = computed(() => isEditMode.value ? "사건 정보 수정" : "신규 사건 등록");
const pageDescription = computed(() => isEditMode.value ? "등록된 사건 정보를 확인하고 수정합니다." : "필수 입력값 검증과 등록 확인 모달을 제공합니다.");
const submitText = computed(() => {
  if (submitting.value) return isEditMode.value ? "저장 중" : "등록 중";
  return isEditMode.value ? "사건 정보 저장" : "사건 등록 · ID 발급";
});
const confirmTitle = computed(() => isEditMode.value ? "사건 정보를 저장할까요?" : "사건을 등록할까요?");
const confirmMessage = computed(() => isEditMode.value ? "수정한 사건 정보가 저장됩니다." : "기본 사건 정보를 등록한 뒤 사진을 업로드합니다.");
const ageLabel = computed(() => {
  const year = Number(form.birthYear);
  if (!year || year < 1900) return "";
  return `${currentYear - year + 1}세 추정`;
});
const syncAgeFromBirthYear = () => {
  const year = Number(form.birthYear);
  if (year >= 1900 && year <= currentYear) form.age = String(currentYear - year + 1);
};
const syncBirthYearFromAge = () => {
  const age = Number(form.age);
  if (age > 0 && age < 130) form.birthYear = String(currentYear - age + 1);
};

const appearanceKeys = ["head", "face", "top", "bottom", "shoes", "accessory", "body", "feature"];
const acceptedPhotoTypes = new Set(["image/jpeg", "image/png", "image/webp"]);
const maxPhotoBytes = 10 * 1024 * 1024;

const snapshotForm = () => JSON.parse(JSON.stringify({
  ...form,
  photoFile: null
}));

const validate = () => {
  errors.value = {};
  const requiredFields = [
    "reporterName",
    "reporterPhone",
    "name",
    "birthYear",
    "lastSeenDate",
    "lastSeenTime",
    "lastSeenLocation",
    "story"
  ];
  requiredFields.forEach((key) => {
    if (!String(form[key] ?? "").trim()) errors.value[key] = "필수 입력값입니다.";
  });

  const phoneDigits = String(form.reporterPhone).replace(/\D/g, "");
  if (form.reporterPhone && (!/^[0-9 -]+$/.test(form.reporterPhone) || !/^\d{10,11}$/.test(phoneDigits))) {
    errors.value.reporterPhone = "전화번호 형식이 올바르지 않습니다.";
  }

  const birthYear = Number(form.birthYear);
  if (form.birthYear && (!Number.isInteger(birthYear) || birthYear < 1900 || birthYear > currentYear)) {
    errors.value.birthYear = `1900년부터 ${currentYear}년 사이로 입력해 주세요.`;
  }

  if (!appearanceKeys.some((key) => String(form[key] ?? "").trim())) {
    errors.value.appearance = "인상착의 항목을 하나 이상 입력해 주세요.";
  }

  if (!isEditMode.value && !form.photoFile) {
    errors.value.photo = "사진을 선택해 주세요.";
  }

  if (form.photoFile && !acceptedPhotoTypes.has(form.photoFile.type)) {
    errors.value.photo = "JPEG, PNG, WebP 이미지만 업로드할 수 있습니다.";
  } else if (form.photoFile?.size > maxPhotoBytes) {
    errors.value.photo = "사진은 10MB 이하여야 합니다.";
  }

  return Object.keys(errors.value).length === 0;
};

const setPhoto = (file) => {
  if (!file || isClosed.value || submitting.value || deletingPhoto.value) return;
  errors.value.photo = "";
  photoError.value = "";
  if (!acceptedPhotoTypes.has(file.type)) {
    errors.value.photo = "JPEG, PNG, WebP 이미지만 업로드할 수 있습니다.";
    return;
  }
  if (file.size > maxPhotoBytes) {
    errors.value.photo = "사진은 10MB 이하여야 합니다.";
    return;
  }
  if (photoObjectUrl) URL.revokeObjectURL(photoObjectUrl);
  form.photoFile = file;
  form.photo = file.name;
  photoObjectUrl = URL.createObjectURL(file);
  photoPreviewUrl.value = photoObjectUrl;
};

const onPhotoChange = (event) => setPhoto(event.target.files?.[0]);
const onPhotoDrop = (event) => setPhoto(event.dataTransfer.files?.[0]);

const saveDraft = () => {
  const draft = { ...form, photoFile: null, photo: "" };
  localStorage.setItem("eyes-for-u-case-draft", JSON.stringify(draft));
  draftSaved.value = true;
  window.setTimeout(() => { draftSaved.value = false; }, 1800);
};

const submit = () => {
  if (submitting.value || deletingPhoto.value || isClosed.value) return;
  operationError.value = "";
  if (validate()) confirmOpen.value = true;
};

const closeConfirm = () => {
  if (!submitting.value) confirmOpen.value = false;
};

const loadCase = async () => {
  const requestId = ++loadRequestId;
  loadError.value = "";
  operationError.value = "";
  photoError.value = "";

  if (!isEditMode.value) {
    if (photoObjectUrl) {
      URL.revokeObjectURL(photoObjectUrl);
      photoObjectUrl = "";
    }
    Object.assign(form, createEmptyForm());
    initialForm.value = null;
    existingPhotoUrl.value = "";
    caseStatus.value = null;
    photoPreviewUrl.value = "";
    errors.value = {};
    loading.value = false;
    return;
  }

  loading.value = true;
  try {
    const detail = await getCase(route.params.caseId);
    if (requestId !== loadRequestId) return;
    if (photoObjectUrl) {
      URL.revokeObjectURL(photoObjectUrl);
      photoObjectUrl = "";
    }
    photoPreviewUrl.value = "";
    Object.assign(form, createEmptyForm(), caseDetailToForm(detail), { photoFile: null });
    initialForm.value = snapshotForm();
    existingPhotoUrl.value = detail.photoUrl || "";
    form.photo = detail.photoUrl ? "등록된 사진" : "";
    caseStatus.value = detail.status;
    if (route.query.photoUpload === "failed") {
      const loadedCaseLabel = [detail.caseNumber, `ID ${detail.id ?? route.params.caseId}`]
        .filter(Boolean)
        .join(" · ");
      photoError.value = pendingPhotoError.value
        || `${loadedCaseLabel} 사건은 등록됐지만 사진 업로드에 실패했습니다. 사진을 다시 선택해 업로드해 주세요.`;
      pendingPhotoError.value = "";
    }
  } catch (error) {
    if (requestId !== loadRequestId) return;
    loadError.value = error?.message || "사건 정보를 불러오지 못했습니다.";
  } finally {
    if (requestId === loadRequestId) loading.value = false;
  }
};

watch(() => route.params.caseId, () => {
  submitRequestId += 1;
  confirmOpen.value = false;
  loadCase();
}, { immediate: true });

const persist = async () => {
  if (submitting.value || deletingPhoto.value) return;
  const requestId = ++submitRequestId;
  const editCaseId = route.params.caseId == null ? null : String(route.params.caseId);
  const selectedPhoto = form.photoFile;
  const isCurrentRequest = () => requestId === submitRequestId;
  submitting.value = true;
  operationError.value = "";
  photoError.value = "";

  try {
    if (!editCaseId) {
      const created = await createCase(buildCreateCasePayload(form));
      try {
        await putCasePhoto(created.id, selectedPhoto);
      } catch (error) {
        if (!isCurrentRequest()) return;
        const createdCaseLabel = [created.caseNumber, `ID ${created.id}`].filter(Boolean).join(" · ");
        pendingPhotoError.value = `${createdCaseLabel} 사건은 등록됐지만 사진 업로드에 실패했습니다. ${error?.message || "사진을 다시 선택해 업로드해 주세요."}`;
        localStorage.removeItem("eyes-for-u-case-draft");
        confirmOpen.value = false;
        await router.replace({
          path: `/admin/cases/${created.id}/edit`,
          query: { photoUpload: "failed" }
        });
        return;
      }

      localStorage.removeItem("eyes-for-u-case-draft");
      if (!isCurrentRequest()) return;
      confirmOpen.value = false;
      await router.push(`/admin/cases/${created.id}`);
      return;
    }

    const patch = buildCaseUpdatePatch(initialForm.value, form);
    const hasBasicChanges = Object.keys(patch).length > 0;
    if (!hasBasicChanges && !form.photoFile) {
      operationError.value = "변경된 내용이 없습니다.";
      confirmOpen.value = false;
      return;
    }

    if (hasBasicChanges) {
      const updated = await updateCase(editCaseId, patch);
      if (isCurrentRequest()) {
        Object.assign(form, caseDetailToForm(updated), { photoFile: selectedPhoto });
        initialForm.value = snapshotForm();
        existingPhotoUrl.value = updated.photoUrl || existingPhotoUrl.value;
        caseStatus.value = updated.status;
      }
    }

    if (selectedPhoto) {
      try {
        const photo = await putCasePhoto(editCaseId, selectedPhoto);
        if (isCurrentRequest()) existingPhotoUrl.value = photo.photoUrl;
      } catch (error) {
        if (!isCurrentRequest()) return;
        photoError.value = hasBasicChanges
          ? `기본 정보는 저장됐지만 사진 업로드에 실패했습니다. ${error?.message || ""}`.trim()
          : error?.message || "사진 업로드에 실패했습니다.";
        confirmOpen.value = false;
        return;
      }
    }

    localStorage.removeItem("eyes-for-u-case-draft");
    if (!isCurrentRequest()) return;
    confirmOpen.value = false;
    await router.push(`/admin/cases/${editCaseId}`);
  } catch (error) {
    if (isCurrentRequest()) {
      operationError.value = error?.message || "사건 정보를 저장하지 못했습니다.";
      confirmOpen.value = false;
    }
  } finally {
    submitting.value = false;
  }
};

const removePhoto = async () => {
  if (!isEditMode.value || !existingPhotoUrl.value || deletingPhoto.value || submitting.value) return;
  if (!window.confirm("등록된 사진을 삭제할까요?")) return;

  const caseId = String(route.params.caseId);
  const loadContextId = loadRequestId;
  deletingPhoto.value = true;
  photoError.value = "";
  try {
    await deleteCasePhoto(caseId);
    if (loadContextId !== loadRequestId || String(route.params.caseId) !== caseId) return;
    existingPhotoUrl.value = "";
    form.photo = "";
    form.photoFile = null;
    photoPreviewUrl.value = "";
    if (photoObjectUrl) {
      URL.revokeObjectURL(photoObjectUrl);
      photoObjectUrl = "";
    }
  } catch (error) {
    if (loadContextId === loadRequestId && String(route.params.caseId) === caseId) {
      photoError.value = error?.message || "사진을 삭제하지 못했습니다.";
    }
  } finally {
    deletingPhoto.value = false;
  }
};

onBeforeUnmount(() => {
  submitRequestId += 1;
  loadRequestId += 1;
  if (photoObjectUrl) URL.revokeObjectURL(photoObjectUrl);
});
</script>

<template>
  <section class="content-panel form-page wide-form-page">
    <div class="section-heading">
      <div>
        <h2>{{ pageTitle }}</h2>
        <p>{{ pageDescription }}</p>
      </div>
    </div>

    <div v-if="loading" class="state-view"><strong>사건 정보를 불러오는 중입니다.</strong></div>
    <div v-else-if="loadError" class="state-view error">
      <strong>{{ loadError }}</strong>
      <div class="form-actions">
        <button @click="loadCase">다시 시도</button>
        <button class="ghost-button" @click="router.push('/admin/cases')">목록으로</button>
      </div>
    </div>

    <template v-else>
      <div v-if="isClosed" class="form-error">종료된 사건의 기본 정보와 사진은 교체할 수 없습니다. 기존 사진 삭제만 가능합니다.</div>
      <div v-if="operationError" class="form-error">{{ operationError }}</div>

      <div class="form-grid case-form-grid">
      <section>
        <h3>신고자 정보</h3>
        <label class="required-field"><span class="field-title">신고자 이름</span><input v-model="form.reporterName" :disabled="isClosed || submitting" /><small>{{ errors.reporterName }}</small></label>
        <label class="required-field"><span class="field-title">연락처</span><input v-model="form.reporterPhone" :disabled="isClosed || submitting" placeholder="010-0000-0000" /><small>{{ errors.reporterPhone }}</small></label>
        <label>실종자와 관계<input v-model="form.relation" :disabled="isClosed || submitting" placeholder="예: 아들, 보호자, 지인" /></label>
      </section>

      <section>
        <h3>실종자 기본 정보</h3>
        <label class="required-field"><span class="field-title">이름</span><input v-model="form.name" :disabled="isClosed || submitting" /><small>{{ errors.name }}</small></label>
        <label>성별<select v-model="form.gender" :disabled="isClosed || submitting"><option>여</option><option>남</option><option>확인 필요</option></select></label>
        <div class="age-pair">
          <label class="required-field"><span class="field-title">년생</span><input v-model="form.birthYear" :disabled="isClosed || submitting" inputmode="numeric" placeholder="예: 1952" @input="syncAgeFromBirthYear" /><small>{{ errors.birthYear }}</small></label>
          <label><span class="field-title">나이</span><input v-model="form.age" :disabled="isClosed || submitting" inputmode="numeric" placeholder="예: 74" @input="syncBirthYearFromAge" /><small>{{ ageLabel }}</small></label>
        </div>
        <label class="required-field"><span class="field-title">사진 업로드</span>
          <input ref="fileInput" class="visually-hidden" type="file" accept="image/jpeg,image/png,image/webp" :disabled="isClosed || submitting || deletingPhoto" @change="onPhotoChange" />
          <button :class="['file-dropzone', photoDisplayUrl && 'has-preview']" type="button" :disabled="isClosed || submitting || deletingPhoto" @click="fileInput?.click()" @dragover.prevent @drop.prevent="onPhotoDrop">
            <img v-if="photoDisplayUrl" :src="photoDisplayUrl" alt="등록된 실종자 사진" />
            <span v-else>{{ form.photo || "사진을 선택하거나 이 영역에 드래그하세요" }}</span>
            <FolderOpen v-if="!photoDisplayUrl" :size="18" />
          </button>
          <small>{{ errors.photo }}</small>
        </label>
        <div v-if="existingPhotoUrl" class="form-actions">
          <button class="ghost-button" type="button" :disabled="deletingPhoto || submitting" @click="removePhoto">{{ deletingPhoto ? "삭제 중" : "기존 사진 삭제" }}</button>
        </div>
        <div v-if="photoError" class="form-error">{{ photoError }}</div>
      </section>

      <section class="wide appearance-section">
        <h3>인상착의</h3>
        <div class="appearance-layout">
          <div class="person-preview" aria-hidden="true">
            <span class="person-head"></span>
            <span class="person-body"></span>
            <span class="person-arm left"></span>
            <span class="person-arm right"></span>
            <span class="person-leg left"></span>
            <span class="person-leg right"></span>
            <span class="person-shoe left"></span>
            <span class="person-shoe right"></span>
          </div>
          <div class="appearance-fields">
            <div class="body-side-fields">
              <label class="head-field">머리<input v-model="form.head" :disabled="isClosed || submitting" placeholder="예: 흰머리, 짧은 검정 머리" /></label>
              <label class="top-field">상의<input v-model="form.top" :disabled="isClosed || submitting" placeholder="예: 검은색 패딩, 남색 후드티" /></label>
              <label class="bottom-field">하의<input v-model="form.bottom" :disabled="isClosed || submitting" placeholder="예: 회색 바지, 청바지" /></label>
              <label class="shoes-field">신발<input v-model="form.shoes" :disabled="isClosed || submitting" placeholder="예: 흰 운동화, 검정 스니커즈" /></label>
            </div>
            <div class="appearance-extra-fields">
              <label>얼굴 특징<input v-model="form.face" :disabled="isClosed || submitting" placeholder="예: 둥근 얼굴, 안경, 수염" /></label>
              <label>가방/소지품<input v-model="form.accessory" :disabled="isClosed || submitting" placeholder="예: 지팡이, 빨간 백팩, 보행보조기" /></label>
              <label>체형<input v-model="form.body" :disabled="isClosed || submitting" placeholder="예: 마른 체형, 보통 체형, 허리가 굽음" /></label>
              <label>추가 설명<textarea v-model="form.feature" :disabled="isClosed || submitting" placeholder="예: 회색 지팡이를 짚고 걸음, 오른쪽 다리를 절음" /></label>
            </div>
          </div>
        </div>
        <small class="form-error">{{ errors.appearance }}</small>
      </section>

      <section class="wide">
        <h3>실종 정보 및 탐색 조건</h3>
        <div class="inline-grid">
          <label class="required-field"><span class="field-title">마지막 목격 날짜</span><input v-model="form.lastSeenDate" type="date" :disabled="isClosed || submitting" /><small>{{ errors.lastSeenDate }}</small></label>
          <label class="required-field"><span class="field-title">마지막 목격 시간</span><input v-model="form.lastSeenTime" type="time" :disabled="isClosed || submitting" /><small>{{ errors.lastSeenTime }}</small></label>
          <label class="required-field address-field"><span class="field-title">마지막 목격 위치</span>
            <div class="address-input"><input v-model="form.lastSeenLocation" :disabled="isClosed || submitting" placeholder="도로명, 건물명, 지번을 정확히 입력" /><MapPin :size="16" /></div>
            <small>{{ errors.lastSeenLocation }}</small>
          </label>
        </div>
        <label class="required-field"><span class="field-title">실종 경위</span><textarea v-model="form.story" :disabled="isClosed || submitting" placeholder="신고자가 설명한 실종 경위를 입력하세요." /><small>{{ errors.story }}</small></label>
        <p>탐색 조건 API 연결 후 제공됩니다. 아래 항목은 현재 서버에 저장되지 않습니다.</p>
        <label>자연어 탐색 문장
          <textarea v-model="form.prompt" disabled placeholder="예: 70대 여성, 검은색 패딩과 회색 바지를 착용, 지팡이 소지" />
        </label>
        <label>제외 조건<input v-model="form.exclude" disabled placeholder="예: 검은 모자 착용자는 제외, 유모차 동반자는 제외" /></label>
        <div class="inline-grid">
          <label>영상 조회 시작 기준<select v-model="form.searchFrom" disabled><option>신고 접수 시각</option><option>마지막 목격 시각</option><option>현재 시각</option><option>직접 입력</option></select><div class="custom-datetime"><input v-model="form.searchFromCustomDate" type="date" disabled /><input v-model="form.searchFromCustomTime" type="time" disabled /></div></label>
          <label>영상 조회 종료 기준<select v-model="form.searchTo" disabled><option>신고 접수 시각</option><option>마지막 목격 시각</option><option>현재 시각</option><option>직접 입력</option></select><div class="custom-datetime"><input v-model="form.searchToCustomDate" type="date" disabled /><input v-model="form.searchToCustomTime" type="time" disabled /></div></label>
          <label>우선 탐색 범위<select v-model="form.zones" disabled><option>마지막 목격 위치 주변</option><option>전체 CCTV 구역</option><option>Zone A</option><option>Zone B</option><option>주요 이동 경로 우선</option></select></label>
        </div>
      </section>
      </div>

      <div class="form-actions">
        <button class="ghost-button" :disabled="submitting" @click="router.back()">취소</button>
        <button class="ghost-button" :disabled="isClosed || submitting || deletingPhoto" @click="saveDraft">임시저장</button>
        <button class="primary-button" :disabled="isClosed || submitting || deletingPhoto" @click="submit">{{ submitText }}</button>
        <span v-if="draftSaved" class="draft-saved">임시저장됨</span>
      </div>
      <ConfirmModal
        :open="confirmOpen"
        :title="confirmTitle"
        :message="confirmMessage"
        :confirm-text="isEditMode ? '저장' : '등록'"
        :loading="submitting"
        :confirm-disabled="submitting"
        @close="closeConfirm"
        @confirm="persist"
      />
    </template>
  </section>
</template>
