<script setup>
import { computed } from "vue";

const props = defineProps({
  open: Boolean,
  title: String,
  message: String,
  confirmText: { type: String, default: "확인" },
  showReason: { type: Boolean, default: false },
  reason: { type: String, default: "" },
  reasonError: { type: String, default: "" },
  loading: { type: Boolean, default: false },
  confirmDisabled: { type: Boolean, default: false }
});
const emit = defineEmits(["close", "confirm", "update:reason"]);

const reasonModel = computed({
  get: () => props.reason,
  set: (value) => emit("update:reason", value)
});

const close = () => {
  if (!props.loading) emit("close");
};

const confirm = () => {
  if (!props.loading && !props.confirmDisabled) emit("confirm", props.reason);
};
</script>

<template>
  <div v-if="open" class="modal-backdrop" @click.self="close">
    <section class="modal" role="dialog" aria-modal="true" :aria-labelledby="title ? 'confirm-modal-title' : undefined">
      <h3 id="confirm-modal-title">{{ title }}</h3>
      <p>{{ message }}</p>
      <label v-if="showReason" class="modal-reason-field">
        <span>사유</span>
        <textarea
          v-model="reasonModel"
          placeholder="변경 사유를 입력하세요"
          maxlength="1000"
          :aria-invalid="Boolean(reasonError)"
          :aria-describedby="reasonError ? 'confirm-modal-reason-error' : undefined"
          :disabled="loading"
        />
        <small v-if="reasonError" id="confirm-modal-reason-error" class="modal-reason-error">{{ reasonError }}</small>
      </label>
      <div class="modal-actions">
        <button class="ghost-button" :disabled="loading" @click="close">취소</button>
        <button class="primary-button" :disabled="loading || confirmDisabled" @click="confirm">
          {{ loading ? "처리 중..." : confirmText }}
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.modal-reason-field {
  display: grid;
  gap: 6px;
  margin-top: 16px;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
}

.modal-reason-error {
  color: #b23b32;
  font-size: 12px;
  font-weight: 600;
}

button:disabled,
textarea:disabled {
  cursor: not-allowed;
  opacity: .6;
}
</style>
