<script setup>
import { computed, nextTick, reactive, ref, watch } from "vue";

const ZONE_OPTIONS = {
  head: ["안경", "선글라스", "마스크", "모자", "긴머리", "짧은머리", "묶은머리", "곱슬머리", "흰머리", "대머리", "수염", "점·흉터"],
  top: ["티셔츠", "셔츠", "후드티", "니트", "가디건", "조끼", "재킷", "점퍼", "패딩", "코트", "정장"],
  bottom: ["청바지", "면바지", "슬랙스", "반바지", "치마", "레깅스", "트레이닝복", "작업복", "정장바지"],
  shoes: ["운동화", "구두", "로퍼", "샌들", "슬리퍼", "부츠", "장화", "등산화", "안전화", "맨발"],
};

const FORM_OPTIONS = {
  head: [],
  top: ["긴팔", "반팔", "민소매"],
  bottom: ["긴바지", "7부바지", "긴치마", "짧은치마"],
  shoes: [],
};

const COLOR_OPTIONS = [
  "검정", "흰색", "회색", "빨강", "주황", "노랑", "초록", "파랑",
  "남색", "보라", "분홍", "갈색", "베이지", "아이보리", "하늘색",
];

const ZONE_LABELS = {
  head: "머리 · 얼굴",
  top: "상의",
  bottom: "하의",
  shoes: "신발",
};

const STATUS_STEPS = [
  { label: "접수", time: "2026/07/24 AM 10:32", desc: "신고가 접수되어 사건이 등록되었습니다." },
  { label: "탐색중", time: "2026/07/24 AM 10:35", desc: "AI가 녹화 영상과 실시간 영상을 탐색하고 있습니다." },
  { label: "후보확인", time: "예정", desc: "관제자가 유력 후보를 검토하고 있습니다." },
  { label: "수색진행", time: "예정", desc: "확인된 목격 정보를 바탕으로 수색을 진행 중입니다." },
  { label: "종료", time: "예정", desc: "사건이 종료되었습니다." },
];

const CASE_CODE = "MP-2026-0417";
const DEMO_PHONE = "010-1234-5678";

const activeScreen = ref("report");
const activeZone = ref(null);
const copied = ref(false);
const selectedPhoto = ref("");
const photoInput = ref(null);
const photoUnavailable = ref(false);
const photoError = ref("");
const mapContainer = ref(null);
const mapMessage = ref("");
const submittedPhone = ref("");
const lookupResultVisible = ref(false);
const lookupError = ref("");
const appearance = reactive({ head: [], top: [], bottom: [], shoes: [] });
const appearanceForms = reactive({ head: {}, top: {}, bottom: {}, shoes: {} });
const appearanceColors = reactive({ head: {}, top: {}, bottom: {}, shoes: {} });
const appearanceNotes = reactive({ head: "", top: "", bottom: "", shoes: "" });
const reporter = reactive({ phone: "", emailLocal: "", emailDomain: "" });
const missing = reactive({
  name: "",
  gender: "",
  ageGroup: "",
  lastSeenTime: "",
  lastSeenPlace: "",
});
const lookup = reactive({ code: "", phone: "" });
let copyTimer;
let mapSearchTimer;
let kakaoMap;
let kakaoMarker;

const KAKAO_MAP_APP_KEY = import.meta.env.VITE_KAKAO_MAP_APP_KEY || "";

const activeFeatureOptions = computed(() =>
  activeZone.value ? ZONE_OPTIONS[activeZone.value] : [],
);

const activeFormOptions = computed(() =>
  activeZone.value ? FORM_OPTIONS[activeZone.value] : [],
);

const reportTabActive = computed(() => activeScreen.value !== "status");

const pageHeading = computed(() =>
  activeScreen.value === "status" ? "사건 조회" : "실종자 신고",
);

const pageDescription = computed(() =>
  activeScreen.value === "status"
    ? "접수 시 발급받은 조회번호로 진행 상태를 확인하세요."
    : "관제실 탐색에 필요한 정보를 입력해 주세요.",
);

const lastSeenTimeDisplay = computed(() => {
  if (!missing.lastSeenTime) return "";
  const [date, time] = missing.lastSeenTime.split("T");
  const [year, month, day] = date.split("-");
  const [hour, minute] = time.split(":");
  const hourNumber = Number(hour);
  const period = hourNumber < 12 ? "오전" : "오후";
  const displayHour = hourNumber % 12 || 12;
  return `${year}/${month}/${day} ${period} ${displayHour}:${minute}`;
});

const kakaoMapSearchUrl = computed(() =>
  `https://map.kakao.com/link/search/${encodeURIComponent(missing.lastSeenPlace.trim())}`,
);

function setScreen(screen) {
  activeScreen.value = screen;
  if (screen === "status") clearLookupResult();
}

function goToMissingForm() {
  activeScreen.value = "missing";
}

function submitReport() {
  if (!selectedPhoto.value && !photoUnavailable.value) {
    photoError.value = "사진을 등록하거나 ‘사진을 확보하지 못했습니다’를 선택해 주세요.";
    return;
  }
  submittedPhone.value = normalizePhone(reporter.phone);
  activeScreen.value = "submitted";
}

function goToStatus() {
  lookup.code = CASE_CODE;
  lookup.phone = submittedPhone.value.replace(/\D/g, "");
  lookupResultVisible.value = false;
  lookupError.value = "";
  activeScreen.value = "status";
}

function normalizePhone(value) {
  const digits = value.replace(/\D/g, "");
  return digits.length === 11
    ? `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7)}`
    : value.trim();
}

function clearLookupResult() {
  lookupResultVisible.value = false;
  lookupError.value = "";
}

function sanitizeReporterPhone() {
  reporter.phone = reporter.phone.replace(/\D/g, "").slice(0, 11);
}

function sanitizeLookupPhone() {
  lookup.phone = lookup.phone.replace(/\D/g, "").slice(0, 11);
  clearLookupResult();
}

function sanitizeAge() {
  missing.ageGroup = String(missing.ageGroup ?? "").replace(/\D/g, "").slice(0, 3);
}

function submitLookup() {
  lookup.code = lookup.code.trim().toUpperCase();
  const expectedPhone = submittedPhone.value || DEMO_PHONE;

  if (lookup.code === CASE_CODE && normalizePhone(lookup.phone) === expectedPhone) {
    lookupResultVisible.value = true;
    lookupError.value = "";
    return;
  }

  lookupResultVisible.value = false;
  lookupError.value = "조회번호 또는 신고자 전화번호를 확인해 주세요.";
}

function toggleZone(zone) {
  activeZone.value = activeZone.value === zone ? null : zone;
}

function toggleOption(option) {
  const values = appearance[activeZone.value];
  const index = values.indexOf(option);
  if (index === -1) values.push(option);
  else {
    values.splice(index, 1);
    delete appearanceColors[activeZone.value][option];
  }
}

function appearanceItems(zone) {
  const selected = appearance[zone];
  return selected.map((feature) => ({
    key: feature,
    label: feature,
  }));
}

function appearanceSummary(zone) {
  const values = appearanceItems(zone).map(({ key, label }) =>
    appearanceColors[zone][key]
      ? `${label} (${appearanceColors[zone][key]})`
      : label,
  );
  const note = appearanceNotes[zone].trim();
  if (note) values.push(note);
  return values.length ? values.join(", ") : "선택 안 함";
}

function removeAppearance(feature) {
  if (activeZone.value && appearance[activeZone.value].includes(feature)) {
    toggleOption(feature);
  }
}

function choosePhoto() {
  photoInput.value?.click();
}

function setPhoto(file) {
  if (!file?.type.startsWith("image/")) return;
  if (selectedPhoto.value) URL.revokeObjectURL(selectedPhoto.value);
  selectedPhoto.value = URL.createObjectURL(file);
  photoUnavailable.value = false;
  photoError.value = "";
}

function onPhotoChange(event) {
  setPhoto(event.target.files?.[0]);
}

function onPhotoDrop(event) {
  setPhoto(event.dataTransfer.files?.[0]);
}

function togglePhotoUnavailable() {
  photoError.value = "";
  if (!photoUnavailable.value) return;
  if (selectedPhoto.value) URL.revokeObjectURL(selectedPhoto.value);
  selectedPhoto.value = "";
  if (photoInput.value) photoInput.value.value = "";
}

function loadKakaoMaps() {
  if (window.kakao?.maps?.services) return Promise.resolve(window.kakao);

  return new Promise((resolve, reject) => {
    const existing = document.querySelector("script[data-kakao-map-sdk]");
    if (existing) {
      existing.addEventListener("load", () => window.kakao.maps.load(() => resolve(window.kakao)), { once: true });
      existing.addEventListener("error", reject, { once: true });
      return;
    }

    const script = document.createElement("script");
    script.dataset.kakaoMapSdk = "true";
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${KAKAO_MAP_APP_KEY}&libraries=services&autoload=false`;
    script.onload = () => window.kakao.maps.load(() => resolve(window.kakao));
    script.onerror = reject;
    document.head.appendChild(script);
  });
}

async function showAddressOnMap(address) {
  if (!KAKAO_MAP_APP_KEY) {
    mapMessage.value = "카카오맵에서 입력한 주소를 확인할 수 있습니다.";
    return;
  }

  try {
    const kakao = await loadKakaoMaps();
    if (!mapContainer.value) return;
    if (!kakaoMap) {
      kakaoMap = new kakao.maps.Map(mapContainer.value, {
        center: new kakao.maps.LatLng(37.5665, 126.978),
        level: 4,
      });
    }
    const geocoder = new kakao.maps.services.Geocoder();
    geocoder.addressSearch(address, (result, status) => {
      if (status !== kakao.maps.services.Status.OK) {
        mapMessage.value = "정확한 도로명 또는 지번 주소를 입력해 주세요.";
        return;
      }
      const position = new kakao.maps.LatLng(result[0].y, result[0].x);
      if (kakaoMarker) kakaoMarker.setMap(null);
      kakaoMarker = new kakao.maps.Marker({ map: kakaoMap, position });
      kakaoMap.setCenter(position);
      mapMessage.value = "입력한 마지막 목격 위치입니다.";
    });
  } catch {
    mapMessage.value = "지도를 불러오지 못했습니다. 카카오맵에서 주소를 확인해 주세요.";
  }
}

watch(
  () => missing.lastSeenPlace,
  (address) => {
    clearTimeout(mapSearchTimer);
    mapMessage.value = "";
    if (address.trim().length < 2) return;
    mapSearchTimer = setTimeout(async () => {
      await nextTick();
      showAddressOnMap(address.trim());
    }, 500);
  },
  { flush: "post" },
);

async function copyCode() {
  try {
    await navigator.clipboard?.writeText(CASE_CODE);
  } catch {
    // Local environments can deny clipboard access; feedback is still shown.
  }
  copied.value = true;
  clearTimeout(copyTimer);
  copyTimer = setTimeout(() => (copied.value = false), 1500);
}
</script>

<template>
  <main class="app-shell">
    <section class="mobile-page">
      <header class="header">
        <div class="brand-row">
          <div class="brand-logo" aria-hidden="true">
            <img src="/assets/eyesonu-logo.png" alt="" />
          </div>
          <strong class="brand-name">Eyes On U</strong>
        </div>
        <nav class="header-tabs" aria-label="주요 화면 선택">
          <button type="button" :class="{ active: reportTabActive }" @click="setScreen('report')">신고하기</button>
          <button type="button" :class="{ active: activeScreen === 'status' }" @click="setScreen('status')">사건조회</button>
        </nav>
      </header>

      <div class="content">
        <section v-if="activeScreen !== 'submitted'" class="page-intro">
          <h1>{{ pageHeading }}</h1>
          <p>{{ pageDescription }}</p>

          <ol v-if="reportTabActive" class="progress-steps" aria-label="신고 진행 단계">
            <li :class="{ active: activeScreen === 'report', complete: activeScreen === 'missing' }">
              <span>{{ activeScreen === 'missing' ? '✓' : '1' }}</span>
              <strong>신고자 정보</strong>
            </li>
            <li :class="{ active: activeScreen === 'missing' }">
              <span>2</span>
              <strong>실종자 정보</strong>
            </li>
          </ol>
        </section>

        <section v-if="activeScreen === 'report' || activeScreen === 'missing'" class="screen">
          <div class="emergency-notice">
            <span class="notice-icon" aria-hidden="true">i</span>
            <p><strong>위급한 상황이라면 먼저 112에 신고해 주세요.</strong><br />이 서비스는 관제실 탐색을 위한 정보 등록 서비스입니다.</p>
          </div>

          <form class="screen" @submit.prevent="goToMissingForm">
            <article class="card">
              <h2>연락처</h2>
              <label>
                <span class="label-row"><span>전화번호 <b>*</b></span></span>
                <input v-model="reporter.phone" type="tel" inputmode="numeric" maxlength="11" pattern="010[0-9]{8}" required @input="sanitizeReporterPhone" />
              </label>
              <label>
                <span class="label-row"><span>이메일</span><small>선택</small></span>
                <div class="email-field">
                  <input v-model="reporter.emailLocal" type="text" inputmode="email" aria-label="이메일 아이디" />
                  <span aria-hidden="true">@</span>
                  <select v-model="reporter.emailDomain" aria-label="이메일 도메인">
                    <option value="" disabled>도메인 선택</option>
                    <option value="naver.com">naver.com</option>
                    <option value="gmail.com">gmail.com</option>
                    <option value="daum.net">daum.net</option>
                    <option value="kakao.com">kakao.com</option>
                    <option value="hanmail.net">hanmail.net</option>
                    <option value="outlook.com">outlook.com</option>
                  </select>
                </div>
              </label>
            </article>
            <div v-if="activeScreen === 'report'" class="action-row"><button class="primary-button" type="submit">다음 단계 <span aria-hidden="true">↓</span></button></div>
          </form>

          <form v-if="activeScreen === 'missing'" class="screen missing-form" @submit.prevent="submitReport">
            <div class="section-divider"><span>실종자 정보를 입력해 주세요</span></div>

            <article class="card">
            <h2>실종자 기본 정보</h2>
            <label><span class="label-row"><span>이름 <b>*</b></span></span><input v-model="missing.name" type="text" placeholder="홍길동" required /></label>
            <div class="two-columns">
              <label>
                <span class="label-row"><span>성별 <b>*</b></span></span>
                <select v-model="missing.gender" required>
                  <option value="" disabled>선택해 주세요</option>
                  <option value="여성">여성</option>
                  <option value="남성">남성</option>
                  <option value="기타">기타</option>
                  <option value="확인불가">확인 불가</option>
                </select>
              </label>
              <label>
                <span class="label-row"><span>나이 <b>*</b></span></span>
                <div class="input-suffix"><input v-model="missing.ageGroup" type="text" inputmode="numeric" maxlength="3" placeholder="75" required @input="sanitizeAge" /><span>세</span></div>
              </label>
            </div>
            <label>
              <span class="label-row"><span>실종자 사진 <b>*</b></span></span>
              <small class="field-help">사진은 AI 탐색 정확도를 높이는 가장 중요한 정보입니다. 얼굴이 잘 보이는 최근 사진을 등록해 주세요.</small>
              <input ref="photoInput" class="visually-hidden" type="file" accept="image/*" tabindex="-1" aria-hidden="true" @change="onPhotoChange" />
              <button
                class="photo-dropzone"
                :class="{ error: photoError }"
                type="button"
                @click="choosePhoto"
                @dragover.prevent
                @drop.prevent="onPhotoDrop"
              >
                <img v-if="selectedPhoto" :src="selectedPhoto" alt="선택한 실종자 사진" />
                <span v-else>사진을 끌어다 놓거나 선택하세요</span>
              </button>
            </label>
            <label class="checkbox-row">
              <input v-model="photoUnavailable" type="checkbox" @change="togglePhotoUnavailable" />
              <span>실종자 사진을 확보하지 못했습니다</span>
            </label>
            <p v-if="photoError" class="form-error" role="alert">{{ photoError }}</p>
            </article>

            <article class="card appearance-card">
            <h2>인상착의 — 부위를 눌러 선택하세요</h2>
            <div class="appearance-picker">
              <div class="person-figure" aria-label="인상착의 부위 선택">
                <button class="body-zone head" :class="{ filled: appearance.head.length }" type="button" aria-label="머리 얼굴" @click="toggleZone('head')"><span /></button>
                <button class="body-zone top" :class="{ filled: appearance.top.length }" type="button" aria-label="상의" @click="toggleZone('top')">
                  <span class="arm left" /><span class="torso" /><span class="arm right" />
                </button>
                <button class="body-zone bottom" :class="{ filled: appearance.bottom.length }" type="button" aria-label="하의" @click="toggleZone('bottom')"><span /><span /></button>
                <button class="body-zone shoes" :class="{ filled: appearance.shoes.length }" type="button" aria-label="신발" @click="toggleZone('shoes')"><span /><span /></button>
              </div>

              <div class="zone-summary">
                <button
                  v-for="(label, zone) in ZONE_LABELS"
                  :key="zone"
                  type="button"
                  :class="{ active: activeZone === zone }"
                  @click="toggleZone(zone)"
                >
                  <strong>{{ label }}</strong>
                  <span>{{ appearanceSummary(zone) }}</span>
                </button>
              </div>
            </div>

            <div v-if="activeZone" class="option-panel">
              <strong>{{ ZONE_LABELS[activeZone] }} 선택 (중복 가능)</strong>
              <div class="option-group feature-options">
                <span class="option-section-title">특징 선택</span>
                <div class="chips">
                  <button
                    v-for="option in activeFeatureOptions"
                    :key="option"
                    type="button"
                    :class="{ selected: appearance[activeZone].includes(option) }"
                    @click="toggleOption(option)"
                  >
                    {{ option }}
                  </button>
                </div>
              </div>
              <div v-if="appearance[activeZone].length" class="selected-appearance-list">
                <span class="option-section-title">선택한 특징 설정</span>
                <div
                  v-for="item in appearanceItems(activeZone)"
                  :key="item.key"
                  class="selected-appearance-row"
                >
                  <span class="appearance-feature-name">{{ item.label }}</span>
                  <select
                    v-if="activeFormOptions.length"
                    v-model="appearanceForms[activeZone][item.key]"
                    :aria-label="`${item.key} 형태 선택`"
                  >
                    <option value="">형태 선택</option>
                    <option v-for="form in activeFormOptions" :key="form" :value="form">{{ form }}</option>
                  </select>
                  <span v-else class="selection-spacer" aria-hidden="true" />
                  <select v-model="appearanceColors[activeZone][item.key]" :aria-label="`${item.label} 색상 선택`">
                    <option value="">색상 선택</option>
                    <option v-for="color in COLOR_OPTIONS" :key="color" :value="color">{{ color }}</option>
                  </select>
                  <button class="remove-appearance" type="button" :aria-label="`${item.key} 삭제`" @click="removeAppearance(item.key)">×</button>
                </div>
              </div>
              <label class="custom-appearance">
                <span class="option-section-title">목록에 없는 특징이나 색상 직접 입력</span>
                <input v-model="appearanceNotes[activeZone]" type="text" :placeholder="`${ZONE_LABELS[activeZone]}의 무늬, 특징 또는 기타 색상을 입력하세요`" />
              </label>
            </div>
            </article>

            <article class="card">
            <h2>마지막 목격 정보</h2>
            <label><span class="label-row"><span>마지막 목격 시각 <b>*</b></span></span><div class="datetime-field"><input v-model="missing.lastSeenTime" class="datetime-input" type="datetime-local" required /><span class="datetime-display" :class="{ empty: !missing.lastSeenTime }">{{ lastSeenTimeDisplay || "년/월/일 오전(오후) 시:분" }}</span></div></label>
            <label><span class="label-row"><span>마지막 목격 장소 <b>*</b></span></span><input v-model="missing.lastSeenPlace" type="text" placeholder="서울시 강남구 테헤란로 152" required /></label>
            <div v-if="missing.lastSeenPlace.trim()" class="map-block">
              <div ref="mapContainer" class="kakao-map" :class="{ fallback: !KAKAO_MAP_APP_KEY }">
                <div v-if="!KAKAO_MAP_APP_KEY" class="map-fallback-copy"><strong>Kakao Maps</strong><span>{{ missing.lastSeenPlace }}</span></div>
              </div>
              <div class="map-meta"><span>{{ mapMessage || '주소를 확인하고 있습니다.' }}</span><a :href="kakaoMapSearchUrl" target="_blank" rel="noopener noreferrer">카카오맵에서 확인 ↗</a></div>
            </div>
            </article>

            <div class="action-row"><button class="primary-button submit" type="submit">신고 접수하기</button></div>
          </form>
        </section>

        <section v-else-if="activeScreen === 'submitted'" class="submitted-screen">
          <div class="success-icon"><span /></div>
          <div class="submitted-copy">
            <h2>신고가 접수되었습니다</h2>
            <p>관제실에서 신고 내용을 확인한 뒤 영상 탐색을 시작합니다.</p>
          </div>
          <div class="submission-notice">
            <strong>조회번호와 신고자 전화번호를 함께 보관해 주세요.</strong>
            <ul>
              <li>사건조회 화면에서 두 정보를 입력하면 진행 상태를 확인할 수 있습니다.</li>
              <li>접수 완료와 주요 상태 변경 안내는 등록한 전화번호로 알림톡으로 제공됩니다.</li>
            </ul>
          </div>
          <article class="code-card">
            <span>사건 조회번호</span>
            <div class="code-row">
              <strong>{{ CASE_CODE }}</strong>
              <button class="copy-button" type="button" title="복사하기" aria-label="조회번호 복사" @click="copyCode"><span /><i /></button>
            </div>
            <small v-if="copied">복사되었습니다</small>
          </article>
          <button class="primary-button full" type="button" @click="goToStatus">사건 진행상태 확인하기</button>
        </section>

        <section v-else class="screen">
          <form class="card lookup-card" @submit.prevent="submitLookup">
            <h2>조회 정보</h2>
            <label>
              사건 조회번호
              <input v-model="lookup.code" class="monospace" type="text" required @input="clearLookupResult" />
            </label>
            <label>
              신고자 전화번호
              <input v-model="lookup.phone" type="tel" inputmode="numeric" maxlength="11" pattern="010[0-9]{8}" required @input="sanitizeLookupPhone" />
            </label>
            <p v-if="lookupError" class="form-error" role="alert">{{ lookupError }}</p>
            <div class="action-row"><button class="primary-button lookup" type="submit">조회하기</button></div>
          </form>

          <article v-if="lookupResultVisible" class="card status-card">
            <h2>{{ missing.name || '박순자' }} 님 사건 · {{ CASE_CODE }}</h2>
            <div class="timeline">
              <div v-for="(step, index) in STATUS_STEPS" :key="step.label" class="timeline-step" :class="{ done: index <= 1, current: index === 1 }">
                <div class="timeline-marker"><span /><i v-if="index < STATUS_STEPS.length - 1" /></div>
                <div class="timeline-copy"><div class="timeline-title"><strong>{{ step.label }}</strong><time>{{ step.time }}</time></div><p>{{ step.desc }}</p></div>
              </div>
            </div>
          </article>
        </section>
      </div>
    </section>
  </main>
</template>
