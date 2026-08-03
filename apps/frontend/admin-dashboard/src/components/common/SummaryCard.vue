<script setup>
defineProps({ item: { type: Object, required: true } });
</script>

<template>
  <article class="summary-card compact">
    <p>{{ item.title }}</p>
    <strong>{{ Number(item.value).toLocaleString() }}</strong>
    <span v-if="item.delta !== null && item.delta !== undefined" :class="Number(item.delta) < 0 ? 'down' : 'up'">{{ item.delta }} 전일 대비</span>
    <span v-else>현재 DB 기준</span>
  </article>
</template>
