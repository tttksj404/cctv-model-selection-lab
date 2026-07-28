<script setup>
import { computed } from "vue";
import LastSeenPlaceField from "./LastSeenPlaceField.vue";

const lastSeenTime = defineModel("time", { default: "" });
const lastSeenPlace = defineModel("place", { default: "" });

const lastSeenTimeDisplay = computed(() => {
  if (!lastSeenTime.value) return "";

  const [date, time] = lastSeenTime.value.split("T");
  const [year, month, day] = date.split("-");
  const [hour, minute] = time.split(":");
  const hourNumber = Number(hour);
  const period = hourNumber < 12 ? "오전" : "오후";

  return `${year}/${month}/${day} ${period} ${hourNumber % 12 || 12}:${minute}`;
});
</script>

<template>
  <article class="card">
    <h2>마지막 목격 정보</h2>

    <label>
      <span class="label-row">
        <span>마지막 목격 시각 <b>*</b></span>
      </span>
      <div class="datetime-field">
        <input
          v-model="lastSeenTime"
          class="datetime-input"
          type="datetime-local"
          required
        />
        <span class="datetime-display" :class="{ empty: !lastSeenTime }">
          {{ lastSeenTimeDisplay || "년/월/일 오전(오후) 시:분" }}
        </span>
      </div>
    </label>

    <LastSeenPlaceField v-model="lastSeenPlace" />
  </article>
</template>
