<script setup>
import { computed, reactive, ref } from "vue";

const ZONE_OPTIONS = {
  head: [
    "안경", "선글라스", "마스크", "모자", "긴머리", "짧은머리",
    "묶은머리", "곱슬머리", "흰머리", "대머리", "수염", "점·흉터",
  ],
  top: [
    "티셔츠", "셔츠", "후드티", "니트", "가디건", "조끼",
    "재킷", "점퍼", "패딩", "코트", "정장",
  ],
  bottom: [
    "청바지", "면바지", "슬랙스", "반바지", "치마", "레깅스",
    "트레이닝복", "작업복", "정장바지",
  ],
  shoes: [
    "운동화", "구두", "로퍼", "샌들", "슬리퍼", "부츠",
    "장화", "등산화", "안전화", "맨발",
  ],
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

const activeZone = ref(null);
const appearance = reactive({ head: [], top: [], bottom: [], shoes: [] });
const appearanceForms = reactive({ head: {}, top: {}, bottom: {}, shoes: {} });
const appearanceColors = reactive({ head: {}, top: {}, bottom: {}, shoes: {} });
const appearanceNotes = reactive({ head: "", top: "", bottom: "", shoes: "" });

const activeFeatureOptions = computed(() =>
  activeZone.value ? ZONE_OPTIONS[activeZone.value] : [],
);

const activeFormOptions = computed(() =>
  activeZone.value ? FORM_OPTIONS[activeZone.value] : [],
);

function toggleZone(zone) {
  activeZone.value = activeZone.value === zone ? null : zone;
}

function toggleOption(option) {
  const values = appearance[activeZone.value];
  const index = values.indexOf(option);

  if (index === -1) {
    values.push(option);
    appearanceForms[activeZone.value][option] = "";
    appearanceColors[activeZone.value][option] = "";
  } else {
    values.splice(index, 1);
    delete appearanceColors[activeZone.value][option];
    delete appearanceForms[activeZone.value][option];
  }
}

function appearanceItems(zone) {
  return appearance[zone].map((feature) => ({ key: feature, label: feature }));
}

function appearanceSummary(zone) {
  const values = appearanceItems(zone).map(({ key, label }) => {
    const properties = [
      appearanceForms[zone][key],
      appearanceColors[zone][key],
    ].filter(Boolean);

    return properties.length ? `${label} (${properties.join(", ")})` : label;
  });
  const note = appearanceNotes[zone].trim();

  if (note) values.push(note);
  return values.length ? values.join(", ") : "선택 안 함";
}

function removeAppearance(feature) {
  if (activeZone.value && appearance[activeZone.value].includes(feature)) {
    toggleOption(feature);
  }
}
</script>

<template>
  <article class="card appearance-card">
    <h2>인상착의 — 부위를 눌러 선택하세요</h2>

    <div class="appearance-picker">
      <div class="person-figure" aria-label="인상착의 부위 선택">
        <button class="body-zone head" :class="{ filled: appearance.head.length }" type="button" aria-label="머리 얼굴" @click="toggleZone('head')">
          <span />
        </button>
        <button class="body-zone top" :class="{ filled: appearance.top.length }" type="button" aria-label="상의" @click="toggleZone('top')">
          <span class="arm left" /><span class="torso" /><span class="arm right" />
        </button>
        <button class="body-zone bottom" :class="{ filled: appearance.bottom.length }" type="button" aria-label="하의" @click="toggleZone('bottom')">
          <span /><span />
        </button>
        <button class="body-zone shoes" :class="{ filled: appearance.shoes.length }" type="button" aria-label="신발" @click="toggleZone('shoes')">
          <span /><span />
        </button>
      </div>

      <div class="zone-summary">
        <button v-for="(label, zone) in ZONE_LABELS" :key="zone" type="button" :class="{ active: activeZone === zone }" @click="toggleZone(zone)">
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
          <button v-for="option in activeFeatureOptions" :key="option" type="button" :class="{ selected: appearance[activeZone].includes(option) }" @click="toggleOption(option)">
            {{ option }}
          </button>
        </div>
      </div>

      <div v-if="appearance[activeZone].length" class="selected-appearance-list">
        <span class="option-section-title">선택한 특징 설정</span>
        <div v-for="item in appearanceItems(activeZone)" :key="item.key" class="selected-appearance-row">
          <span class="appearance-feature-name">{{ item.label }}</span>
          <select
            v-if="activeFormOptions.length"
            :value="appearanceForms[activeZone][item.key] || ''"
            :class="{
              'has-selection': appearanceForms[activeZone][item.key],
            }"
            :aria-label="`${item.key} 형태 선택`"
            @change="
              appearanceForms[activeZone][item.key] = $event.target.value
            "
          >
            <option value="" disabled>형태 선택</option>
            <option value="안함">안함</option>
            <option v-for="form in activeFormOptions" :key="form" :value="form">{{ form }}</option>
          </select>
          <span v-else class="selection-spacer" aria-hidden="true" />
          <select
            :value="appearanceColors[activeZone][item.key] || ''"
            :class="{
              'has-selection': appearanceColors[activeZone][item.key],
            }"
            :aria-label="`${item.label} 색상 선택`"
            @change="
              appearanceColors[activeZone][item.key] = $event.target.value
            "
          >
            <option value="" disabled>색상 선택</option>
            <option value="안함">안함</option>
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
</template>
