<script setup>
import { computed, reactive, ref, useId, watch } from "vue";
import {
  APPEARANCE_CATEGORIES,
  APPEARANCE_KEYS,
  APPEARANCE_LIMITS,
  COLOR_OPTIONS,
  getAppearanceCategory,
  parseAppearanceValue,
  serializeAppearanceState
} from "../../domain/appearancePicker";

const props = defineProps({
  modelValue: {
    type: Object,
    default: () => ({})
  },
  disabled: {
    type: Boolean,
    default: false
  },
  errors: {
    type: Object,
    default: () => ({})
  }
});

const emit = defineEmits(["update:modelValue"]);

const activeCategoryKey = ref(null);
const componentId = useId();
const selfEmittedValues = new Map();
const states = reactive(
  Object.fromEntries(
    APPEARANCE_KEYS.map((key) => [key, { items: [], note: "" }])
  )
);

const activeCategory = computed(() =>
  activeCategoryKey.value
    ? getAppearanceCategory(activeCategoryKey.value)
    : undefined
);
const activeState = computed(() =>
  activeCategoryKey.value ? states[activeCategoryKey.value] : undefined
);

function cloneParsedState(key, value) {
  const source = String(value ?? "");
  const parsed = parseAppearanceValue(key, source);
  const items = Array.isArray(parsed.items)
    ? parsed.items.map(({ feature, form, color }) => ({
      feature: String(feature ?? ""),
      form: String(form ?? ""),
      color: String(color ?? "")
    }))
    : [];

  // A completely unknown legacy value belongs in the direct-entry control. Keep
  // its exact whitespace in the editor, while the domain serializer remains the
  // source of truth for values changed by the user.
  const parsedNote = String(parsed.note ?? "");
  const note = items.length === 0 && parsedNote === source.trim()
    ? source
    : parsedNote;

  return { items, note };
}

watch(
  () => APPEARANCE_KEYS.map((key) => props.modelValue?.[key] ?? ""),
  (values) => {
    APPEARANCE_KEYS.forEach((key, index) => {
      const incomingValue = String(values[index] ?? "");

      // Skip the model echo from this component so in-progress note whitespace
      // is not normalized. Any different external value still rehydrates the
      // category, including route-to-route resets.
      if (selfEmittedValues.get(key) === incomingValue) {
        selfEmittedValues.delete(key);
        return;
      }

      selfEmittedValues.delete(key);
      states[key] = cloneParsedState(key, incomingValue);
    });
  },
  { immediate: true, flush: "sync" }
);

function panelId(key) {
  return `${componentId}-${key}-panel`;
}

function categoryButtonId(key) {
  return `${componentId}-${key}-category`;
}

function countId(key) {
  return `${componentId}-${key}-count`;
}

function errorId(key) {
  return `${componentId}-${key}-error`;
}

function serializeCategory(key) {
  return serializeAppearanceState(states[key]);
}

function categorySummary(key) {
  return serializeCategory(key) || "선택 안 함";
}

function hasCategoryValue(key) {
  return Boolean(serializeCategory(key));
}

function categoryLength(key) {
  return serializeCategory(key).length;
}

function remainingCharacters(key) {
  return APPEARANCE_LIMITS[key] - categoryLength(key);
}

function remainingText(key) {
  const remaining = remainingCharacters(key);
  return remaining >= 0
    ? `${remaining}자 남음`
    : `${Math.abs(remaining)}자 초과`;
}

function normalizeError(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item ?? "").trim()).filter(Boolean);
  }
  const message = String(value ?? "").trim();
  return message ? [message] : [];
}

function categoryErrors(key) {
  const messages = [];
  const remaining = remainingCharacters(key);

  if (remaining < 0) {
    messages.push(
      `${getAppearanceCategory(key)?.label ?? key} 항목은 최대 ${APPEARANCE_LIMITS[key]}자까지 입력할 수 있습니다. (${Math.abs(remaining)}자 초과)`
    );
  }

  for (const message of normalizeError(props.errors?.[key])) {
    if (!messages.includes(message)) messages.push(message);
  }

  return messages;
}

function categoryHasError(key) {
  return categoryErrors(key).length > 0;
}

function optionMetadata(key, feature) {
  return getAppearanceCategory(key)?.options.find(
    (option) => option.label === feature
  );
}

function itemIsSelected(key, feature) {
  return states[key].items.some((item) => item.feature === feature);
}

function toggleCategory(key) {
  activeCategoryKey.value = activeCategoryKey.value === key ? null : key;
}

function commitCategory(key) {
  const serialized = serializeCategory(key);
  selfEmittedValues.set(key, serialized);
  emit("update:modelValue", {
    ...(props.modelValue ?? {}),
    [key]: serialized
  });
}

function toggleFeature(key, feature) {
  if (props.disabled) return;
  const items = states[key].items;
  const index = items.findIndex((item) => item.feature === feature);

  if (index === -1) {
    items.push({ feature, form: "", color: "" });
  } else {
    items.splice(index, 1);
  }

  commitCategory(key);
}

function removeFeature(key, feature) {
  if (props.disabled) return;
  const index = states[key].items.findIndex(
    (item) => item.feature === feature
  );
  if (index === -1) return;
  states[key].items.splice(index, 1);
  commitCategory(key);
}

function updateItemProperty(key, feature, property, value) {
  if (props.disabled || !["form", "color"].includes(property)) return;
  const item = states[key].items.find(
    (candidate) => candidate.feature === feature
  );
  if (!item) return;
  item[property] = String(value ?? "");
  commitCategory(key);
}

function updateNote(key, value) {
  if (props.disabled) return;
  states[key].note = String(value ?? "");
  commitCategory(key);
}

function noteMaxLength(key) {
  const state = states[key];
  const withoutNote = serializeAppearanceState({
    items: state.items,
    note: ""
  });
  const withMarker = serializeAppearanceState({
    items: state.items,
    note: "가"
  });
  const separatorLength = Math.max(
    0,
    withMarker.length - withoutNote.length - 1
  );
  const available = Math.max(
    0,
    APPEARANCE_LIMITS[key] - withoutNote.length - separatorLength
  );

  // Browsers do not truncate a value when maxlength becomes shorter. Keeping
  // the current length here also lets an overlong legacy value be edited down.
  return Math.max(available, String(state.note ?? "").length);
}
</script>

<template>
  <div class="appearance-picker" data-testid="appearance-picker">
    <p class="appearance-picker__instruction">
      인상착의 항목을 선택한 뒤 형태와 색상을 추가하세요. 목록에 없는 내용은 직접 입력할 수 있습니다.
    </p>

    <div class="appearance-picker__overview">
      <div
        class="appearance-picker__figure"
        role="img"
        aria-label="인상착의 사람 실루엣"
      >
        <span
          class="appearance-picker__figure-head"
          :class="{ 'is-filled': hasCategoryValue('head') || hasCategoryValue('face') }"
        />
        <span
          class="appearance-picker__figure-body"
          :class="{ 'is-filled': hasCategoryValue('top') }"
        />
        <span
          class="appearance-picker__figure-arm appearance-picker__figure-arm--left"
          :class="{ 'is-filled': hasCategoryValue('top') || hasCategoryValue('accessory') }"
        />
        <span
          class="appearance-picker__figure-arm appearance-picker__figure-arm--right"
          :class="{ 'is-filled': hasCategoryValue('top') || hasCategoryValue('accessory') }"
        />
        <span
          class="appearance-picker__figure-leg appearance-picker__figure-leg--left"
          :class="{ 'is-filled': hasCategoryValue('bottom') || hasCategoryValue('body') }"
        />
        <span
          class="appearance-picker__figure-leg appearance-picker__figure-leg--right"
          :class="{ 'is-filled': hasCategoryValue('bottom') || hasCategoryValue('body') }"
        />
        <span
          class="appearance-picker__figure-shoe appearance-picker__figure-shoe--left"
          :class="{ 'is-filled': hasCategoryValue('shoes') }"
        />
        <span
          class="appearance-picker__figure-shoe appearance-picker__figure-shoe--right"
          :class="{ 'is-filled': hasCategoryValue('shoes') }"
        />
      </div>

      <div class="appearance-picker__summaries">
        <button
          v-for="category in APPEARANCE_CATEGORIES"
          :id="categoryButtonId(category.key)"
          :key="category.key"
          type="button"
          class="appearance-picker__category"
          :class="{
            'is-active': activeCategoryKey === category.key,
            'is-filled': hasCategoryValue(category.key),
            'has-error': categoryHasError(category.key)
          }"
          :aria-expanded="activeCategoryKey === category.key"
          :aria-controls="panelId(category.key)"
          :aria-invalid="categoryHasError(category.key) ? 'true' : undefined"
          :data-appearance-category="category.key"
          @click="toggleCategory(category.key)"
        >
          <span class="appearance-picker__category-heading">
            <strong>{{ category.label }}</strong>
            <span v-if="hasCategoryValue(category.key)" aria-hidden="true">입력됨</span>
          </span>
          <span class="appearance-picker__summary">
            {{ categorySummary(category.key) }}
          </span>
          <span
            v-if="categoryHasError(category.key)"
            class="appearance-picker__summary-error"
            :data-appearance-error="category.key"
          >
            {{ categoryErrors(category.key)[0] }}
          </span>
        </button>
      </div>
    </div>

    <section
      v-if="activeCategory && activeState"
      :id="panelId(activeCategory.key)"
      class="appearance-picker__panel"
      :aria-labelledby="categoryButtonId(activeCategory.key)"
      :data-appearance-panel="activeCategory.key"
    >
      <div class="appearance-picker__panel-heading">
        <div>
          <h4>{{ activeCategory.label }} 선택</h4>
          <p>여러 특징을 함께 선택할 수 있습니다.</p>
        </div>
        <span class="appearance-picker__selected-count">
          {{ activeState.items.length }}개 선택
        </span>
      </div>

      <fieldset class="appearance-picker__feature-group" :disabled="disabled">
        <legend>특징 선택</legend>
        <div class="appearance-picker__chips">
          <button
            v-for="option in activeCategory.options"
            :key="option.label"
            type="button"
            class="appearance-picker__chip"
            :class="{ 'is-selected': itemIsSelected(activeCategory.key, option.label) }"
            :disabled="disabled"
            :aria-pressed="itemIsSelected(activeCategory.key, option.label)"
            :data-appearance-feature="option.label"
            :data-category="activeCategory.key"
            @click="toggleFeature(activeCategory.key, option.label)"
          >
            {{ option.label }}
          </button>
        </div>
      </fieldset>

      <div
        v-if="activeState.items.length"
        class="appearance-picker__selected-list"
      >
        <strong class="appearance-picker__subheading">선택한 특징 설정</strong>
        <div
          v-for="item in activeState.items"
          :key="item.feature"
          class="appearance-picker__selected-row"
          :data-appearance-row="item.feature"
        >
          <span class="appearance-picker__feature-name">{{ item.feature }}</span>

          <label
            v-if="optionMetadata(activeCategory.key, item.feature)?.forms?.length"
            class="appearance-picker__select-field"
          >
            <span>형태</span>
            <select
              :value="item.form"
              :disabled="disabled"
              :aria-label="`${item.feature} 형태`"
              data-appearance-property="form"
              :data-feature="item.feature"
              @change="updateItemProperty(activeCategory.key, item.feature, 'form', $event.target.value)"
            >
              <option value="">미지정</option>
              <option
                v-for="formOption in optionMetadata(activeCategory.key, item.feature).forms"
                :key="formOption"
                :value="formOption"
              >
                {{ formOption }}
              </option>
            </select>
          </label>
          <span v-else class="appearance-picker__select-spacer" aria-hidden="true" />

          <label
            v-if="optionMetadata(activeCategory.key, item.feature)?.allowColor"
            class="appearance-picker__select-field"
          >
            <span>색상</span>
            <select
              :value="item.color"
              :disabled="disabled"
              :aria-label="`${item.feature} 색상`"
              data-appearance-property="color"
              :data-feature="item.feature"
              @change="updateItemProperty(activeCategory.key, item.feature, 'color', $event.target.value)"
            >
              <option value="">미지정</option>
              <option
                v-for="colorOption in COLOR_OPTIONS"
                :key="colorOption"
                :value="colorOption"
              >
                {{ colorOption }}
              </option>
            </select>
          </label>
          <span v-else class="appearance-picker__select-spacer" aria-hidden="true" />

          <button
            type="button"
            class="appearance-picker__remove"
            :disabled="disabled"
            :aria-label="`${item.feature} 제거`"
            data-appearance-remove
            :data-feature="item.feature"
            @click="removeFeature(activeCategory.key, item.feature)"
          >
            제거
          </button>
        </div>
      </div>

      <label class="appearance-picker__note">
        <span class="appearance-picker__subheading">직접 입력</span>
        <textarea
          :value="activeState.note"
          :disabled="disabled"
          :maxlength="noteMaxLength(activeCategory.key)"
          :placeholder="`${activeCategory.label}의 목록에 없는 특징, 무늬 또는 색상을 입력하세요.`"
          :aria-describedby="`${countId(activeCategory.key)} ${categoryHasError(activeCategory.key) ? errorId(activeCategory.key) : ''}`.trim()"
          :aria-invalid="categoryHasError(activeCategory.key) ? 'true' : undefined"
          :data-appearance-note="activeCategory.key"
          @input="updateNote(activeCategory.key, $event.target.value)"
        />
      </label>

      <div
        :id="countId(activeCategory.key)"
        class="appearance-picker__character-status"
        :class="{ 'is-over': remainingCharacters(activeCategory.key) < 0 }"
        aria-live="polite"
      >
        <span :data-appearance-count="activeCategory.key">
          현재 {{ categoryLength(activeCategory.key) }} / 최대 {{ APPEARANCE_LIMITS[activeCategory.key] }}자
        </span>
        <strong :data-appearance-remaining="activeCategory.key">
          {{ remainingText(activeCategory.key) }}
        </strong>
      </div>

      <div
        v-if="categoryHasError(activeCategory.key)"
        :id="errorId(activeCategory.key)"
        class="appearance-picker__errors"
        role="alert"
        :data-appearance-error="activeCategory.key"
      >
        <p v-for="message in categoryErrors(activeCategory.key)" :key="message">
          {{ message }}
        </p>
      </div>
    </section>

    <p
      v-if="errors.appearance"
      class="appearance-picker__global-error"
      role="alert"
      data-appearance-error="appearance"
    >
      {{ errors.appearance }}
    </p>
  </div>
</template>

<style scoped>
.appearance-picker {
  --appearance-accent: #25647f;
  --appearance-accent-strong: #1e5870;
  --appearance-accent-soft: #eef7fa;
  --appearance-border: #d8e0e8;
  --appearance-muted: #64748b;
  --appearance-error: #b23b32;
  display: grid;
  gap: 18px;
  min-width: 0;
  color: #243244;
}

.appearance-picker__instruction {
  margin: 0;
  color: var(--appearance-muted);
  font-size: 13px;
  line-height: 1.55;
}

.appearance-picker__overview {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 28px;
  align-items: center;
  min-width: 0;
}

.appearance-picker__figure {
  position: relative;
  width: 180px;
  height: 330px;
  margin: 0 auto;
}

.appearance-picker__figure span {
  position: absolute;
  display: block;
  background: #d7d2cd;
  transition: background-color 160ms ease, box-shadow 160ms ease;
}

.appearance-picker__figure span.is-filled {
  background: #79aabd;
  box-shadow: inset 0 0 0 1px rgba(30, 88, 112, 0.2);
}

.appearance-picker__figure-head {
  top: 0;
  left: 59px;
  width: 62px;
  height: 62px;
  border-radius: 50%;
}

.appearance-picker__figure-body {
  top: 82px;
  left: 45px;
  width: 90px;
  height: 105px;
  border-radius: 29px 29px 36px 36px;
}

.appearance-picker__figure-arm {
  top: 91px;
  width: 25px;
  height: 91px;
  border-radius: 16px;
}

.appearance-picker__figure-arm--left {
  left: 20px;
  transform: rotate(7deg);
}

.appearance-picker__figure-arm--right {
  right: 20px;
  transform: rotate(-7deg);
}

.appearance-picker__figure-leg {
  top: 174px;
  width: 36px;
  height: 132px;
  border-radius: 0 0 17px 17px;
}

.appearance-picker__figure-leg--left {
  left: 49px;
}

.appearance-picker__figure-leg--right {
  right: 49px;
}

.appearance-picker__figure-shoe {
  top: 302px;
  width: 45px;
  height: 23px;
  border-radius: 8px 8px 12px 12px;
  background: #68635e !important;
}

.appearance-picker__figure-shoe.is-filled {
  background: #315f72 !important;
}

.appearance-picker__figure-shoe--left {
  left: 41px;
}

.appearance-picker__figure-shoe--right {
  right: 41px;
}

.appearance-picker__summaries {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  min-width: 0;
}

.appearance-picker__category {
  width: 100%;
  min-width: 0;
  min-height: 86px;
  padding: 12px 14px;
  border: 1px solid var(--appearance-border);
  border-radius: 8px;
  background: #fff;
  color: #334155;
  text-align: left;
  transition: border-color 140ms ease, background-color 140ms ease, box-shadow 140ms ease;
}

.appearance-picker__category:hover:not(:disabled) {
  border-color: #9dbbc8;
  background: #f9fcfd;
}

.appearance-picker__category:focus-visible,
.appearance-picker__chip:focus-visible,
.appearance-picker__remove:focus-visible,
.appearance-picker__select-field select:focus-visible,
.appearance-picker__note textarea:focus-visible {
  outline: 2px solid #65a4bd;
  outline-offset: 2px;
}

.appearance-picker__category.is-active {
  border-color: var(--appearance-accent);
  background: var(--appearance-accent-soft);
  box-shadow: inset 3px 0 0 var(--appearance-accent);
}

.appearance-picker__category.has-error {
  border-color: #e2a9a4;
}

.appearance-picker__category:disabled,
.appearance-picker__chip:disabled,
.appearance-picker__remove:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.appearance-picker__category-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.appearance-picker__category-heading strong {
  color: #243244;
  font-size: 13px;
}

.appearance-picker__category-heading > span {
  padding: 2px 6px;
  border-radius: 999px;
  color: var(--appearance-accent-strong);
  background: #e0f0f5;
  font-size: 10px;
  font-weight: 800;
}

.appearance-picker__summary {
  display: -webkit-box;
  margin-top: 6px;
  overflow: hidden;
  color: var(--appearance-muted);
  font-size: 12px;
  font-weight: 500;
  line-height: 1.45;
  overflow-wrap: anywhere;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.appearance-picker__category:not(.is-filled) .appearance-picker__summary {
  color: #8b95a3;
}

.appearance-picker__summary-error {
  display: block;
  margin-top: 5px;
  overflow: hidden;
  color: var(--appearance-error);
  font-size: 11px;
  font-weight: 600;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.appearance-picker__panel {
  display: grid;
  gap: 18px;
  padding: 18px;
  border: 1px solid #cbdbe3;
  border-radius: 9px;
  background: #f8fbfc;
  min-width: 0;
}

.appearance-picker__panel-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.appearance-picker__panel-heading h4 {
  margin: 0;
  color: #243244;
  font-size: 14px;
}

.appearance-picker__panel-heading p {
  margin: 4px 0 0;
  color: var(--appearance-muted);
  font-size: 12px;
}

.appearance-picker__selected-count {
  flex: 0 0 auto;
  padding: 4px 8px;
  border-radius: 999px;
  color: var(--appearance-accent-strong);
  background: #e2f0f5;
  font-size: 11px;
  font-weight: 800;
}

.appearance-picker__feature-group {
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}

.appearance-picker__feature-group legend,
.appearance-picker__subheading {
  display: block;
  margin: 0 0 8px;
  color: #4b596a;
  font-size: 12px;
  font-weight: 700;
}

.appearance-picker__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.appearance-picker__chip {
  min-height: 34px;
  padding: 6px 12px;
  border: 1px solid #cfd8e2;
  border-radius: 999px;
  background: #fff;
  color: #475569;
  font-size: 12px;
  font-weight: 700;
}

.appearance-picker__chip:hover:not(:disabled) {
  border-color: #8eb3c2;
  background: #f2f8fa;
}

.appearance-picker__chip.is-selected {
  border-color: var(--appearance-accent);
  color: #fff;
  background: var(--appearance-accent);
}

.appearance-picker__chip.is-selected:hover:not(:disabled) {
  border-color: var(--appearance-accent-strong);
  background: var(--appearance-accent-strong);
}

.appearance-picker__selected-list {
  min-width: 0;
}

.appearance-picker__selected-row {
  display: grid;
  grid-template-columns: minmax(100px, 0.65fr) minmax(130px, 1fr) minmax(130px, 1fr) auto;
  gap: 10px;
  align-items: end;
  min-width: 0;
  padding: 10px 0;
  border-top: 1px solid #e1e8ee;
}

.appearance-picker__selected-row:last-child {
  border-bottom: 1px solid #e1e8ee;
}

.appearance-picker__feature-name {
  align-self: center;
  min-width: 0;
  color: #334155;
  font-size: 13px;
  font-weight: 800;
  overflow-wrap: anywhere;
}

.appearance-picker__select-field {
  display: grid;
  grid-template-rows: auto auto;
  gap: 5px;
  min-width: 0;
  color: var(--appearance-muted);
  font-size: 11px;
  font-weight: 700;
}

.appearance-picker__select-field select {
  width: 100%;
  min-width: 0;
  min-height: 36px;
  border: 1px solid #ccd6e0;
  border-radius: 6px;
  background-color: #fff;
  color: #334155;
  font-size: 12px;
}

.appearance-picker__select-spacer {
  min-width: 0;
}

.appearance-picker__remove {
  min-height: 36px;
  padding: 7px 11px;
  border: 1px solid #dfb6b2;
  border-radius: 6px;
  background: #fff;
  color: #9f3f37;
  font-size: 12px;
  font-weight: 700;
}

.appearance-picker__remove:hover:not(:disabled) {
  background: #fff5f4;
}

.appearance-picker__note {
  display: grid;
  grid-template-rows: auto auto;
  gap: 0;
  min-width: 0;
}

.appearance-picker__note textarea {
  width: 100%;
  min-width: 0;
  min-height: 84px;
  padding: 10px 12px;
  resize: vertical;
  border: 1px solid #ccd6e0;
  border-radius: 6px;
  background: #fff;
  color: #243244;
  font: inherit;
  font-size: 13px;
  line-height: 1.5;
}

.appearance-picker__note textarea[aria-invalid="true"] {
  border-color: #d68f88;
}

.appearance-picker__character-status {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin-top: -10px;
  color: var(--appearance-muted);
  font-size: 11px;
}

.appearance-picker__character-status strong {
  color: #3d6b7f;
}

.appearance-picker__character-status.is-over,
.appearance-picker__character-status.is-over strong {
  color: var(--appearance-error);
}

.appearance-picker__errors {
  display: grid;
  gap: 4px;
  margin-top: -8px;
  color: var(--appearance-error);
  font-size: 12px;
  font-weight: 600;
}

.appearance-picker__errors p,
.appearance-picker__global-error {
  margin: 0;
  line-height: 1.45;
}

.appearance-picker__global-error {
  color: var(--appearance-error);
  font-size: 12px;
  font-weight: 600;
}

@media (max-width: 900px) {
  .appearance-picker__overview {
    grid-template-columns: 1fr;
  }

  .appearance-picker__figure {
    height: 270px;
    transform: scale(0.82);
    transform-origin: top center;
    margin-bottom: -48px;
  }
}

@media (max-width: 640px) {
  .appearance-picker__summaries {
    grid-template-columns: 1fr;
  }

  .appearance-picker__selected-row {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .appearance-picker__select-spacer {
    display: none;
  }

  .appearance-picker__remove {
    justify-self: start;
  }

  .appearance-picker__panel-heading,
  .appearance-picker__character-status {
    align-items: flex-start;
    flex-direction: column;
  }

  .appearance-picker__character-status {
    gap: 3px;
  }
}
</style>
