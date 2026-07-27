<script setup>
import { statusMap } from "../../mocks/mockData";
defineProps({ status: { type: String, required: true } });
</script>

<template>
  <span :class="['status-badge', statusMap[status]?.tone || 'gray']">{{ statusMap[status]?.label || status }}</span>
</template>
