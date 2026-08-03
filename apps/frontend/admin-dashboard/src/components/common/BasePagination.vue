<script setup>
defineProps({ page: Number, totalPages: Number, totalCount: Number, disabled: Boolean });
defineEmits(["update:page"]);
</script>

<template>
  <nav class="pagination" aria-label="페이지 탐색">
    <span>전체 {{ totalCount }}건</span>
    <button type="button" :disabled="disabled || page <= 1" @click="$emit('update:page', page - 1)">이전</button>
    <strong aria-live="polite">{{ page }} / {{ totalPages }}</strong>
    <button type="button" :disabled="disabled || page >= totalPages" @click="$emit('update:page', page + 1)">다음</button>
  </nav>
</template>
