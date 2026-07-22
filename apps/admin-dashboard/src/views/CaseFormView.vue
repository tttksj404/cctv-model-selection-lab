<script setup>
import { computed, reactive, ref } from "vue";
import { FolderOpen, MapPin } from "lucide-vue-next";
import { useRoute, useRouter } from "vue-router";
import { createCase, getCaseDetail } from "../api/mockApi";
import ConfirmModal from "../components/common/ConfirmModal.vue";

const router = useRouter();
const route = useRoute();
const fileInput = ref(null);
const confirmOpen = ref(false);
const draftSaved = ref(false);
const errors = ref({});

const currentYear = new Date().getFullYear();
const form = reactive({
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
const photoPreviewUrl = ref("");

const requiredFields = ["reporterName", "reporterPhone", "name", "birthYear", "lastSeenDate", "lastSeenTime", "lastSeenLocation"];
const isEditMode = computed(() => Boolean(route.params.caseId));
const pageTitle = computed(() => isEditMode.value ? "사건 정보 수정" : "신규 사건 등록");
const pageDescription = computed(() => isEditMode.value ? "등록된 사건 정보를 확인하고 수정합니다." : "필수 입력값 검증과 등록 확인 모달을 제공합니다.");
const submitText = computed(() => isEditMode.value ? "사건 정보 저장" : "사건 등록 · ID 발급");
const confirmTitle = computed(() => isEditMode.value ? "사건 정보를 저장할까요?" : "사건을 등록할까요?");
const confirmMessage = computed(() => isEditMode.value ? "수정한 사건 정보가 저장됩니다." : "입력한 내용으로 서버 전송용 데이터 객체를 생성합니다.");
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
const pad = (value) => String(value).padStart(2, "0");
const toDateTimeParts = (date) => ({
  date: `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`,
  time: `${pad(date.getHours())}:${pad(date.getMinutes())}`
});
const fillSearchDateTime = (target, preset) => {
  if (preset === "직접 입력") return;
  let parts = toDateTimeParts(new Date());
  if (preset === "마지막 목격 시각" && form.lastSeenDate && form.lastSeenTime) {
    parts = { date: form.lastSeenDate, time: form.lastSeenTime };
  }
  if (target === "from") {
    form.searchFromCustomDate = parts.date;
    form.searchFromCustomTime = parts.time;
  } else {
    form.searchToCustomDate = parts.date;
    form.searchToCustomTime = parts.time;
  }
};

const validate = () => {
  errors.value = {};
  requiredFields.forEach((key) => {
    if (!form[key]) errors.value[key] = "필수 입력값입니다.";
  });
  return Object.keys(errors.value).length === 0;
};

const setPhoto = (file) => {
  if (!file) return;
  if (photoPreviewUrl.value) URL.revokeObjectURL(photoPreviewUrl.value);
  form.photoFile = file;
  form.photo = file.name;
  photoPreviewUrl.value = URL.createObjectURL(file);
};

const onPhotoChange = (event) => setPhoto(event.target.files?.[0]);
const onPhotoDrop = (event) => setPhoto(event.dataTransfer.files?.[0]);

const generatePrompt = () => {
  const parts = [
    form.gender && `${form.gender}성`,
    ageLabel.value || (form.birthYear && `${form.birthYear}년생`),
    form.head && `머리/얼굴: ${form.head}`,
    form.face,
    form.top && `상의: ${form.top}`,
    form.bottom && `하의: ${form.bottom}`,
    form.shoes && `신발: ${form.shoes}`,
    form.accessory && `소지품: ${form.accessory}`,
    form.feature && `특징: ${form.feature}`,
    form.lastSeenLocation && `마지막 목격 위치 ${form.lastSeenLocation}`
  ].filter(Boolean);
  form.prompt = parts.join(", ");
};

const saveDraft = () => {
  localStorage.setItem("eyes-for-u-case-draft", JSON.stringify(form));
  draftSaved.value = true;
  window.setTimeout(() => { draftSaved.value = false; }, 1800);
};

const submit = () => {
  if (!form.prompt.trim()) generatePrompt();
  if (validate()) confirmOpen.value = true;
};

if (isEditMode.value) {
  getCaseDetail(route.params.caseId).then((caseItem) => {
    form.reporterName = caseItem.reporter?.split(" / ")[0] || "";
    form.reporterPhone = caseItem.reporter?.split(" / ")[1] || "";
    form.name = caseItem.name || "";
    form.gender = caseItem.gender || "여";
    form.age = caseItem.age ? String(caseItem.age) : "";
    form.birthYear = caseItem.age ? String(currentYear - Number(caseItem.age) + 1) : "";
    form.photo = caseItem.photo || "";
    form.lastSeenDate = caseItem.lastSeenAt?.slice(0, 10) || "";
    form.lastSeenTime = caseItem.lastSeenAt?.slice(11, 16) || "";
    fillSearchDateTime("from", form.searchFrom);
    fillSearchDateTime("to", form.searchTo);
    form.lastSeenLocation = caseItem.lastSeenLocation || "";
    form.feature = caseItem.appearance || "";
  });
}

const create = async () => {
  await createCase({
    ...form,
    age: form.age || ageLabel.value,
    lastSeenAt: `${form.lastSeenDate} ${form.lastSeenTime}`
  });
  localStorage.removeItem("eyes-for-u-case-draft");
  confirmOpen.value = false;
  alert(isEditMode.value ? "사건 정보가 저장되었습니다." : "사건이 등록되었습니다.");
  router.push("/admin/cases");
};
</script>

<template>
  <section class="content-panel form-page wide-form-page">
    <div class="section-heading">
      <div>
        <h2>{{ pageTitle }}</h2>
        <p>{{ pageDescription }}</p>
      </div>
    </div>

    <div class="form-grid case-form-grid">
      <section>
        <h3>신고자 정보</h3>
        <label class="required-field"><span class="field-title">신고자 이름</span><input v-model="form.reporterName" /><small>{{ errors.reporterName }}</small></label>
        <label class="required-field"><span class="field-title">연락처</span><input v-model="form.reporterPhone" placeholder="010-0000-0000" /><small>{{ errors.reporterPhone }}</small></label>
        <label>실종자와 관계<input v-model="form.relation" placeholder="예: 아들, 보호자, 지인" /></label>
      </section>

      <section>
        <h3>실종자 기본 정보</h3>
        <label class="required-field"><span class="field-title">이름</span><input v-model="form.name" /><small>{{ errors.name }}</small></label>
        <label>성별<select v-model="form.gender"><option>여</option><option>남</option><option>확인 필요</option></select></label>
        <div class="age-pair">
          <label class="required-field"><span class="field-title">년생</span><input v-model="form.birthYear" inputmode="numeric" placeholder="예: 1952" @input="syncAgeFromBirthYear" /><small>{{ errors.birthYear }}</small></label>
          <label><span class="field-title">나이</span><input v-model="form.age" inputmode="numeric" placeholder="예: 74" @input="syncBirthYearFromAge" /><small>{{ ageLabel }}</small></label>
        </div>
        <label class="required-field"><span class="field-title">사진 업로드</span>
          <input ref="fileInput" class="visually-hidden" type="file" accept="image/*" @change="onPhotoChange" />
          <button :class="['file-dropzone', photoPreviewUrl && 'has-preview']" type="button" @click="fileInput?.click()" @dragover.prevent @drop.prevent="onPhotoDrop">
            <img v-if="photoPreviewUrl" :src="photoPreviewUrl" alt="업로드한 실종자 사진 미리보기" />
            <span v-else>{{ form.photo || "사진을 선택하거나 이 영역에 드래그하세요" }}</span>
            <FolderOpen v-if="!photoPreviewUrl" :size="18" />
          </button>
        </label>
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
              <label class="head-field">머리<input v-model="form.head" placeholder="예: 흰머리, 짧은 검정 머리" /></label>
              <label class="top-field">상의<input v-model="form.top" placeholder="예: 검은색 패딩, 남색 후드티" /></label>
              <label class="bottom-field">하의<input v-model="form.bottom" placeholder="예: 회색 바지, 청바지" /></label>
              <label class="shoes-field">신발<input v-model="form.shoes" placeholder="예: 흰 운동화, 검정 스니커즈" /></label>
            </div>
            <div class="appearance-extra-fields">
              <label>얼굴 특징<input v-model="form.face" placeholder="예: 둥근 얼굴, 안경, 수염" /></label>
              <label>가방/소지품<input v-model="form.accessory" placeholder="예: 지팡이, 빨간 백팩, 보행보조기" /></label>
              <label>체형<input v-model="form.body" placeholder="예: 마른 체형, 보통 체형, 허리가 굽음" /></label>
              <label>추가 설명<textarea v-model="form.feature" placeholder="예: 회색 지팡이를 짚고 걸음, 오른쪽 다리를 절음" /></label>
            </div>
          </div>
        </div>
      </section>

      <section class="wide">
        <h3>실종 정보 및 탐색 조건</h3>
        <div class="inline-grid">
          <label class="required-field"><span class="field-title">마지막 목격 날짜</span><input v-model="form.lastSeenDate" type="date" /><small>{{ errors.lastSeenDate }}</small></label>
          <label class="required-field"><span class="field-title">마지막 목격 시간</span><input v-model="form.lastSeenTime" type="time" /><small>{{ errors.lastSeenTime }}</small></label>
          <label class="required-field address-field"><span class="field-title">마지막 목격 위치</span>
            <div class="address-input"><input v-model="form.lastSeenLocation" placeholder="도로명, 건물명, 지번을 정확히 입력" /><MapPin :size="16" /></div>
            <small>{{ errors.lastSeenLocation }}</small>
          </label>
        </div>
        <label>실종 경위<textarea v-model="form.story" placeholder="신고자가 설명한 실종 경위를 입력하세요." /></label>
        <label>자연어 탐색 문장
          <textarea v-model="form.prompt" placeholder="예: 70대 여성, 검은색 패딩과 회색 바지를 착용, 지팡이 소지" />
        </label>
        <label>제외 조건<input v-model="form.exclude" placeholder="예: 검은 모자 착용자는 제외, 유모차 동반자는 제외" /></label>
        <div class="inline-grid">
          <label>영상 조회 시작 기준<select v-model="form.searchFrom" @change="fillSearchDateTime('from', form.searchFrom)"><option>신고 접수 시각</option><option>마지막 목격 시각</option><option>현재 시각</option><option>직접 입력</option></select><div class="custom-datetime"><input v-model="form.searchFromCustomDate" type="date" /><input v-model="form.searchFromCustomTime" type="time" /></div></label>
          <label>영상 조회 종료 기준<select v-model="form.searchTo" @change="fillSearchDateTime('to', form.searchTo)"><option>신고 접수 시각</option><option>마지막 목격 시각</option><option>현재 시각</option><option>직접 입력</option></select><div class="custom-datetime"><input v-model="form.searchToCustomDate" type="date" /><input v-model="form.searchToCustomTime" type="time" /></div></label>
          <label>우선 탐색 범위<select v-model="form.zones"><option>마지막 목격 위치 주변</option><option>전체 CCTV 구역</option><option>Zone A</option><option>Zone B</option><option>주요 이동 경로 우선</option></select></label>
        </div>
      </section>
    </div>

    <div class="form-actions">
      <button class="ghost-button" @click="router.back()">취소</button>
      <button class="ghost-button" @click="saveDraft">임시저장</button>
      <button class="primary-button" @click="submit">{{ submitText }}</button>
      <span v-if="draftSaved" class="draft-saved">임시저장됨</span>
    </div>
    <ConfirmModal :open="confirmOpen" :title="confirmTitle" :message="confirmMessage" :confirm-text="isEditMode ? '저장' : '등록'" @close="confirmOpen=false" @confirm="create" />
  </section>
</template>
