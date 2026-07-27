<script setup>
defineProps({ page: Number, totalPages: Number, totalCount: Number });
defineEmits(["update:page"]);
</script>

<template>
  <div class="pagination">
    <span>전체 {{ totalCount }}건</span>
    <button :disabled="page <= 1" @click="$emit('update:page', page - 1)">이전</button>
    <strong>{{ page }} / {{ totalPages }}</strong>
    <button :disabled="page >= totalPages" @click="$emit('update:page', page + 1)">다음</button>
  </div>
</template>
