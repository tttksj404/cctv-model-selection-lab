<script setup>
import { computed, reactive, ref } from "vue";
import AppearanceCard from "./components/AppearanceCard.vue";
import LastSeenCard from "./components/LastSeenCard.vue";

const STATUS_STEPS = [
  {
    label: "접수",
    time: "2026/07/24 AM 10:32",
    desc: "신고가 접수되어 사건이 등록되었습니다.",
  },
  {
    label: "탐색중",
    time: "2026/07/24 AM 10:35",
    desc: "AI가 녹화 영상과 실시간 영상을 탐색하고 있습니다.",
  },
  {
    label: "후보확인",
    time: "예정",
    desc: "관제자가 유력 후보를 검토하고 있습니다.",
  },
  {
    label: "수색진행",
    time: "예정",
    desc: "확인된 목격 정보를 바탕으로 수색을 진행 중입니다.",
  },
  {
    label: "종료",
    time: "예정",
    desc: "사건이 종료되었습니다.",
  },
];

const CASE_CODE = "MP-2026-0417";
const DEMO_PHONE = "010-1234-5678";

const activeScreen = ref("report");
const copied = ref(false);

const selectedPhoto = ref("");
const photoInput = ref(null);
const photoUnavailable = ref(false);
const photoError = ref("");

const submittedPhone = ref("");
const lookupResultVisible = ref(false);
const lookupError = ref("");

const reporter = reactive({
  phone: "",
  emailLocal: "",
  emailDomain: "",
  emailCustomDomain: "",
});

const missing = reactive({
  name: "",
  gender: "",
  ageGroup: "",
  lastSeenTime: "",
  lastSeenPlace: "",
});

const lookup = reactive({
  code: "",
  phone: "",
});

let copyTimer;

const reportTabActive = computed(
  () => activeScreen.value !== "status",
);

const pageHeading = computed(() =>
  activeScreen.value === "status"
    ? "사건 조회"
    : "실종자 신고",
);

const pageDescription = computed(() =>
  activeScreen.value === "status"
    ? "접수 시 발급받은 조회번호로 진행 상태를 확인하세요."
    : "관제실 탐색에 필요한 정보를 입력해 주세요.",
);

function setScreen(screen) {
  activeScreen.value = screen;

  if (screen === "status") {
    clearLookupResult();
  }
}

function goToMissingForm() {
  activeScreen.value = "missing";
}

function submitReport() {
  if (!selectedPhoto.value && !photoUnavailable.value) {
    photoError.value =
      "사진을 등록하거나 ‘사진을 확보하지 못했습니다’를 선택해 주세요.";
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
  reporter.phone = reporter.phone
    .replace(/\D/g, "")
    .slice(0, 11);
}

function sanitizeLookupPhone() {
  lookup.phone = lookup.phone
    .replace(/\D/g, "")
    .slice(0, 11);

  clearLookupResult();
}

function sanitizeAge() {
  missing.ageGroup = String(missing.ageGroup ?? "")
    .replace(/\D/g, "")
    .slice(0, 3);
}

function submitLookup() {
  lookup.code = lookup.code.trim().toUpperCase();

  const expectedPhone =
    submittedPhone.value || DEMO_PHONE;

  if (
    lookup.code === CASE_CODE &&
    normalizePhone(lookup.phone) === expectedPhone
  ) {
    lookupResultVisible.value = true;
    lookupError.value = "";
    return;
  }

  lookupResultVisible.value = false;
  lookupError.value =
    "조회번호 또는 신고자 전화번호를 확인해 주세요.";
}

function choosePhoto() {
  photoInput.value?.click();
}

function setPhoto(file) {
  if (!file?.type.startsWith("image/")) {
    return;
  }

  if (selectedPhoto.value) {
    URL.revokeObjectURL(selectedPhoto.value);
  }

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

  if (!photoUnavailable.value) {
    return;
  }

  if (selectedPhoto.value) {
    URL.revokeObjectURL(selectedPhoto.value);
  }

  selectedPhoto.value = "";

  if (photoInput.value) {
    photoInput.value.value = "";
  }
}

async function copyCode() {
  try {
    await navigator.clipboard?.writeText(
      CASE_CODE,
    );
  } catch {
    // 로컬 환경에서는 클립보드 접근이 거부될 수 있습니다.
  }

  copied.value = true;

  clearTimeout(copyTimer);

  copyTimer = setTimeout(() => {
    copied.value = false;
  }, 1500);
}
</script>

<template>
  <main class="app-shell">
    <section class="mobile-page">
      <header class="header">
        <div class="brand-row">
          <div
            class="brand-logo"
            aria-hidden="true"
          >
            <img
              src="/assets/eyesonu-logo.png"
              alt=""
            />
          </div>

          <strong class="brand-name">
            Eyes On U
          </strong>
        </div>

        <nav
          class="header-tabs"
          aria-label="주요 화면 선택"
        >
          <button
            type="button"
            :class="{ active: reportTabActive }"
            @click="setScreen('report')"
          >
            신고하기
          </button>

          <button
            type="button"
            :class="{
              active: activeScreen === 'status',
            }"
            @click="setScreen('status')"
          >
            사건조회
          </button>
        </nav>
      </header>

      <div class="content">
        <section
          v-if="activeScreen !== 'submitted'"
          class="page-intro"
        >
          <h1>{{ pageHeading }}</h1>
          <p>{{ pageDescription }}</p>

          <ol
            v-if="reportTabActive"
            class="progress-steps"
            aria-label="신고 진행 단계"
          >
            <li
              :class="{
                active:
                  activeScreen === 'report',
                complete:
                  activeScreen === 'missing',
              }"
            >
              <span>
                {{
                  activeScreen === "missing"
                    ? "✓"
                    : "1"
                }}
              </span>
              <strong>신고자 정보</strong>
            </li>

            <li
              :class="{
                active:
                  activeScreen === 'missing',
              }"
            >
              <span>2</span>
              <strong>실종자 정보</strong>
            </li>
          </ol>
        </section>

        <section
          v-if="
            activeScreen === 'report' ||
            activeScreen === 'missing'
          "
          class="screen"
        >
          <div class="emergency-notice">
            <span
              class="notice-icon"
              aria-hidden="true"
            >
              i
            </span>

            <p>
              <strong>
                위급한 상황이라면 먼저 112에
                신고해 주세요.
              </strong>
              <br />
              이 서비스는 관제실 탐색을 위한
              정보 등록 서비스입니다.
            </p>
          </div>

          <form
            class="screen"
            @submit.prevent="goToMissingForm"
          >
            <article class="card">
              <h2>연락처</h2>

              <label>
                <span class="label-row">
                  <span>
                    전화번호 <b>*</b>
                  </span>
                </span>

                <input
                  v-model="reporter.phone"
                  type="tel"
                  inputmode="numeric"
                  maxlength="11"
                  pattern="010[0-9]{8}"
                  required
                  @input="sanitizeReporterPhone"
                />
              </label>

              <label>
                <span class="label-row">
                  <span>이메일</span>
                  <small>선택</small>
                </span>

                <div class="email-field">
                  <input
                    v-model="reporter.emailLocal"
                    type="text"
                    inputmode="email"
                    aria-label="이메일 아이디"
                  />

                  <span aria-hidden="true">@</span>

                  <select
                    v-if="
                      reporter.emailDomain !==
                      'custom'
                    "
                    v-model="reporter.emailDomain"
                    aria-label="이메일 도메인"
                  >
                    <option
                      value=""
                      disabled
                    >
                      도메인 선택
                    </option>
                    <option value="naver.com">
                      naver.com
                    </option>
                    <option value="gmail.com">
                      gmail.com
                    </option>
                    <option value="daum.net">
                      daum.net
                    </option>
                    <option value="kakao.com">
                      kakao.com
                    </option>
                    <option value="hanmail.net">
                      hanmail.net
                    </option>
                    <option value="outlook.com">
                      outlook.com
                    </option>
                    <option value="custom">
                      직접 입력
                    </option>
                  </select>

                  <input
                    v-else
                    v-model="
                      reporter.emailCustomDomain
                    "
                    type="text"
                    inputmode="email"
                    placeholder="직접 입력 (예: example.com)"
                    aria-label="이메일 도메인 직접 입력"
                  />
                </div>
              </label>
            </article>

            <div
              v-if="activeScreen === 'report'"
              class="action-row"
            >
              <button
                class="primary-button"
                type="submit"
              >
                다음 단계
                <span aria-hidden="true">↓</span>
              </button>
            </div>
          </form>

          <form
            v-if="activeScreen === 'missing'"
            class="screen missing-form"
            @submit.prevent="submitReport"
          >
            <div class="section-divider">
              <span>
                실종자 정보를 입력해 주세요
              </span>
            </div>

            <article class="card">
              <h2>실종자 기본 정보</h2>

              <label>
                <span class="label-row">
                  <span>
                    이름 <b>*</b>
                  </span>
                </span>

                <input
                  v-model="missing.name"
                  type="text"
                  placeholder="홍길동"
                  required
                />
              </label>

              <div class="two-columns">
                <label>
                  <span class="label-row">
                    <span>
                      성별 <b>*</b>
                    </span>
                  </span>

                  <select
                    v-model="missing.gender"
                    required
                  >
                    <option
                      value=""
                      disabled
                    >
                      선택해 주세요
                    </option>
                    <option value="여성">
                      여성
                    </option>
                    <option value="남성">
                      남성
                    </option>
                    <option value="기타">
                      기타
                    </option>
                    <option value="확인불가">
                      확인 불가
                    </option>
                  </select>
                </label>

                <label>
                  <span class="label-row">
                    <span>
                      나이 <b>*</b>
                    </span>
                  </span>

                  <div class="input-suffix">
                    <input
                      v-model="missing.ageGroup"
                      type="text"
                      inputmode="numeric"
                      maxlength="3"
                      placeholder="75"
                      required
                      @input="sanitizeAge"
                    />
                    <span>세</span>
                  </div>
                </label>
              </div>

              <label>
                <span class="label-row">
                  <span>
                    실종자 사진 <b>*</b>
                  </span>
                </span>

                <small class="field-help">
                  사진은 AI 탐색 정확도를 높이는
                  가장 중요한 정보입니다. 얼굴이
                  잘 보이는 최근 사진을 등록해
                  주세요.
                </small>

                <input
                  ref="photoInput"
                  class="visually-hidden"
                  type="file"
                  accept="image/*"
                  tabindex="-1"
                  aria-hidden="true"
                  @change="onPhotoChange"
                />

                <button
                  class="photo-dropzone"
                  :class="{ error: photoError }"
                  type="button"
                  @click="choosePhoto"
                  @dragover.prevent
                  @drop.prevent="onPhotoDrop"
                >
                  <img
                    v-if="selectedPhoto"
                    :src="selectedPhoto"
                    alt="선택한 실종자 사진"
                  />

                  <span v-else>
                    사진을 끌어다 놓거나
                    선택하세요
                  </span>
                </button>
              </label>

              <label class="checkbox-row">
                <input
                  v-model="photoUnavailable"
                  type="checkbox"
                  @change="
                    togglePhotoUnavailable
                  "
                />
                <span>
                  실종자 사진을 확보하지
                  못했습니다
                </span>
              </label>

              <p
                v-if="photoError"
                class="form-error"
                role="alert"
              >
                {{ photoError }}
              </p>
            </article>

            <AppearanceCard />

            <LastSeenCard
              v-model:time="missing.lastSeenTime"
              v-model:place="missing.lastSeenPlace"
            />

            <div class="action-row">
              <button
                class="primary-button submit"
                type="submit"
              >
                신고 접수하기
              </button>
            </div>
          </form>
        </section>

        <section
          v-else-if="
            activeScreen === 'submitted'
          "
          class="submitted-screen"
        >
          <div class="success-icon">
            <span />
          </div>

          <div class="submitted-copy">
            <h2>신고가 접수되었습니다</h2>
            <p>
              관제실에서 신고 내용을 확인한 뒤
              영상 탐색을 시작합니다.
            </p>
          </div>

          <div class="submission-notice">
            <strong>
              조회번호와 신고자 전화번호를 함께
              보관해 주세요.
            </strong>

            <ul>
              <li>
                사건조회 화면에서 두 정보를
                입력하면 진행 상태를 확인할 수
                있습니다.
              </li>
              <li>
                접수 완료와 주요 상태 변경
                안내는 등록한 전화번호로
                알림톡으로 제공됩니다.
              </li>
            </ul>
          </div>

          <article class="code-card">
            <span>사건 조회번호</span>

            <div class="code-row">
              <strong>{{ CASE_CODE }}</strong>

              <button
                class="copy-button"
                type="button"
                title="복사하기"
                aria-label="조회번호 복사"
                @click="copyCode"
              >
                <span />
                <i />
              </button>
            </div>

            <small v-if="copied">
              복사되었습니다
            </small>
          </article>

          <button
            class="primary-button full"
            type="button"
            @click="goToStatus"
          >
            사건 진행상태 확인하기
          </button>
        </section>

        <section
          v-else
          class="screen"
        >
          <form
            class="card lookup-card"
            @submit.prevent="submitLookup"
          >
            <h2>조회 정보</h2>

            <label>
              사건 조회번호
              <input
                v-model="lookup.code"
                class="monospace"
                type="text"
                required
                @input="clearLookupResult"
              />
            </label>

            <label>
              신고자 전화번호
              <input
                v-model="lookup.phone"
                type="tel"
                inputmode="numeric"
                maxlength="11"
                pattern="010[0-9]{8}"
                required
                @input="sanitizeLookupPhone"
              />
            </label>

            <p
              v-if="lookupError"
              class="form-error"
              role="alert"
            >
              {{ lookupError }}
            </p>

            <div class="action-row">
              <button
                class="primary-button lookup"
                type="submit"
              >
                조회하기
              </button>
            </div>
          </form>

          <article
            v-if="lookupResultVisible"
            class="card status-card"
          >
            <h2>
              {{ missing.name || "박순자" }} 님
              사건 · {{ CASE_CODE }}
            </h2>

            <div class="timeline">
              <div
                v-for="(
                  step, index
                ) in STATUS_STEPS"
                :key="step.label"
                class="timeline-step"
                :class="{
                  done: index <= 1,
                  current: index === 1,
                }"
              >
                <div
                  class="timeline-marker"
                >
                  <span />
                  <i
                    v-if="
                      index <
                      STATUS_STEPS.length -
                        1
                    "
                  />
                </div>

                <div class="timeline-copy">
                  <div
                    class="timeline-title"
                  >
                    <strong>
                      {{ step.label }}
                    </strong>
                    <time>
                      {{ step.time }}
                    </time>
                  </div>

                  <p>{{ step.desc }}</p>
                </div>
              </div>
            </div>
          </article>
        </section>
      </div>
    </section>
  </main>
</template>
