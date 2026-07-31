<script setup>
import { onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { listCameras } from "../api/cameraApi";
import BasePagination from "../components/common/BasePagination.vue";
import StateBlock from "../components/common/StateBlock.vue";
import StatusBadge from "../components/common/StatusBadge.vue";
import { mapCamera } from "../domain/cameraMapper";

const router = useRouter();
const filters = reactive({ keyword: "", status: "all" });
const rows = ref([]);
const page = ref(1);
const pageSize = 10;
const totalPages = ref(1);
const totalCount = ref(0);
const loading = ref(true);
const error = ref("");
let latestRequestId = 0;

const listParams = () => ({
  status: filters.status === "all" ? undefined : filters.status.toUpperCase(),
  search: filters.keyword.trim() || undefined,
  page: page.value - 1,
  size: pageSize,
  sort: "cameraCode,asc"
});

const load = async () => {
  const requestId = ++latestRequestId;
  loading.value = true;
  error.value = "";

  try {
    const result = await listCameras(listParams());
    if (requestId !== latestRequestId) return;
    rows.value = (result.data || []).map(mapCamera);
    totalPages.value = Math.max(1, result.meta?.totalPages || 0);
    totalCount.value = result.meta?.totalElements || 0;
  } catch (cause) {
    if (requestId !== latestRequestId) return;
    rows.value = [];
    totalPages.value = 1;
    totalCount.value = 0;
    error.value = cause?.message || "CCTV 목록을 불러오지 못했습니다.";
  } finally {
    if (requestId === latestRequestId) loading.value = false;
  }
};

const reset = () => {
  filters.keyword = "";
  filters.status = "all";
};

watch(() => [filters.keyword, filters.status], () => {
  if (page.value !== 1) {
    page.value = 1;
    return;
  }
  load();
});
watch(page, load);
onMounted(load);
onBeforeUnmount(() => { latestRequestId += 1; });
</script>

<template>
  <section class="content-panel">
    <div class="section-heading">
      <div>
        <h2>CCTV 관리</h2>
        <p>실제 등록된 CCTV의 소속, 위치와 연결 상태를 조회합니다.</p>
      </div>
      <button class="primary-button" type="button" @click="router.push('/admin/cameras/new')">
        CCTV 등록
      </button>
    </div>

    <div class="filter-bar">
      <label>검색<input v-model="filters.keyword" placeholder="카메라 코드 또는 이름" /></label>
      <label>
        상태
        <select v-model="filters.status">
          <option value="all">전체</option>
          <option value="online">정상</option>
          <option value="offline">연결 없음</option>
          <option value="error">오류</option>
        </select>
      </label>
      <button class="reset-button" type="button" @click="reset">초기화</button>
    </div>

    <StateBlock :loading="loading" :error="error" :empty="rows.length === 0" @retry="load">
      <div class="table-scroll">
        <table class="case-table">
          <thead>
            <tr>
              <th>코드</th><th>이름</th><th>위치</th><th>위도</th><th>경도</th>
              <th>Media Server</th><th>상태</th><th>마지막 연결</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="camera in rows" :key="camera.id">
              <td class="mono">{{ camera.cameraCode }}</td>
              <td>{{ camera.cameraName }}</td>
              <td>{{ camera.address }}</td>
              <td>{{ camera.latitude }}</td>
              <td>{{ camera.longitude }}</td>
              <td :title="camera.mediaServerCode">{{ camera.mediaServerName }}</td>
              <td><StatusBadge :status="camera.status" /></td>
              <td>{{ camera.lastHeartbeat }}</td>
              <td><button class="ghost-button" @click="router.push(`/admin/cameras/${camera.id}/edit`)">관리</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <BasePagination v-model:page="page" :total-pages="totalPages" :total-count="totalCount" />
    </StateBlock>
  </section>
</template>
