<script setup>
defineProps({ open: Boolean, title: String, message: String, confirmText: { type: String, default: "확인" } });
defineEmits(["close", "confirm"]);
</script>

<template>
  <div v-if="open" class="modal-backdrop" @click.self="$emit('close')">
    <section class="modal">
      <h3>{{ title }}</h3>
      <p>{{ message }}</p>
      <textarea placeholder="변경 사유를 입력하세요"></textarea>
      <div class="modal-actions">
        <button class="ghost-button" @click="$emit('close')">취소</button>
        <button class="primary-button" @click="$emit('confirm')">{{ confirmText }}</button>
      </div>
    </section>
  </div>
</template>
