<script setup>
import { onMounted, ref } from "vue";
import { getLiveFeeds } from "../api/mockApi";
import StatusBadge from "../components/common/StatusBadge.vue";

const feeds = ref([]);
const loading = ref(true);
const error = ref("");

const loadFeeds = async () => {
  loading.value = true;
  error.value = "";

  try {
    feeds.value = await getLiveFeeds();
  } catch (err) {
    error.value = err?.message || "실시간 CCTV 정보를 불러오지 못했습니다.";
  } finally {
    loading.value = false;
  }
};

onMounted(loadFeeds);
</script>

<template>
  <section class="live-monitoring-page">
    <p class="live-description">등록된 CCTV 중 실시간 스트림 4채널을 동시에 확인합니다.</p>

    <div v-if="loading" class="state-view">
      <strong>실시간 CCTV 정보를 불러오는 중입니다.</strong>
    </div>

    <div v-else-if="error" class="state-view error">
      <strong>{{ error }}</strong>
      <button type="button" @click="loadFeeds">다시 시도</button>
    </div>

    <div v-else-if="feeds.length === 0" class="state-view">
      <strong>표시할 실시간 CCTV가 없습니다.</strong>
    </div>

    <div v-else class="live-feed-grid">
      <article v-for="feed in feeds" :key="feed.id" class="live-feed-card">
        <div class="live-feed-frame">
          <div class="live-feed-label">LIVE FEED · {{ feed.name }}</div>
          <div class="live-indicator">
            <span></span>
            <strong>LIVE</strong>
          </div>
          <div class="live-fps">{{ feed.fps }}</div>
        </div>
        <div class="live-feed-meta">
          <div>
            <strong>{{ feed.name }}</strong>
            <span>{{ feed.zone }}</span>
          </div>
          <StatusBadge :status="feed.status" />
        </div>
      </article>
    </div>
  </section>
</template>
