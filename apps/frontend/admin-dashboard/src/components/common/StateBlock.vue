<script setup>
defineProps({ loading: Boolean, error: String, empty: Boolean });
defineEmits(["retry"]);
</script>

<template>
  <div v-if="loading" class="state-view"><strong>데이터를 불러오는 중입니다.</strong></div>
  <div v-else-if="error" class="state-view error">
    <strong>{{ error }}</strong>
    <button @click="$emit('retry')">다시 시도</button>
  </div>
  <div v-else-if="empty" class="state-view">
    <strong>조회된 데이터가 없습니다.</strong>
    <p>검색 조건을 변경하거나 초기화해 주세요.</p>
  </div>
  <slot v-else />
</template>
