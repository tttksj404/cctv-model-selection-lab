<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";

const lastSeenPlace = defineModel({ default: "" });
const mapContainer = ref(null);
const mapMessage = ref("");
const placeSuggestions = ref([]);
const suggestionsVisible = ref(false);
const isSelectingPlace = ref(false);
const KAKAO_MAP_APP_KEY = import.meta.env.VITE_KAKAO_MAP_APP_KEY || "";
const DEFAULT_MAP_CENTER = { latitude: 37.5665, longitude: 126.978 };

let mapSearchTimer;
let placeSearchTimer;
let placeSearchRequestId = 0;
let markerMoveRequestId = 0;
let latestPlaceQuery = "";
let kakaoMap;
let kakaoMapElement;
let kakaoMarker;
let kakaoPlaces;

function clearSuggestionState() {
  placeSuggestions.value = [];
  suggestionsVisible.value = false;
}

const kakaoMapSearchUrl = computed(() =>
  `https://map.kakao.com/link/search/${encodeURIComponent(lastSeenPlace.value.trim())}`,
);

function loadKakaoMaps() {
  if (window.kakao?.maps?.services) return Promise.resolve(window.kakao);

  return new Promise((resolve, reject) => {
    const existing = document.querySelector("script[data-kakao-map-sdk]");

    if (existing) {
      existing.addEventListener(
        "load",
        () => window.kakao.maps.load(() => resolve(window.kakao)),
        { once: true },
      );
      existing.addEventListener("error", reject, { once: true });
      return;
    }

    const script = document.createElement("script");
    script.dataset.kakaoMapSdk = "true";
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${KAKAO_MAP_APP_KEY}&libraries=services&autoload=false`;
    script.onload = () => window.kakao.maps.load(() => resolve(window.kakao));
    script.onerror = reject;
    document.head.appendChild(script);
  });
}

async function initializeMap(kakao, center, level = 4) {
  await nextTick();
  if (!mapContainer.value) return false;

  if (!kakaoMap || kakaoMapElement !== mapContainer.value) {
    if (kakaoMarker) {
      kakaoMarker.setMap(null);
      kakaoMarker = undefined;
    }

    kakaoMapElement = mapContainer.value;
    kakaoMap = new kakao.maps.Map(mapContainer.value, { center, level });
  }
  kakaoMap.relayout();
  kakaoMap.setLevel(level);
  return true;
}

async function showDefaultMap() {
  if (!KAKAO_MAP_APP_KEY) {
    mapMessage.value = "장소를 검색하면 지도에서 위치를 확인할 수 있습니다.";
    return;
  }

  try {
    const kakao = await loadKakaoMaps();
    const center = new kakao.maps.LatLng(
      DEFAULT_MAP_CENTER.latitude,
      DEFAULT_MAP_CENTER.longitude,
    );

    if (!(await initializeMap(kakao, center, 8))) return;

    if (kakaoMarker) {
      kakaoMarker.setMap(null);
      kakaoMarker = undefined;
    }

    kakaoMap.setCenter(center);
    mapMessage.value = "장소명 또는 주소를 검색해 마지막 목격 위치를 지정하세요.";
  } catch {
    mapMessage.value = "기본 지도를 불러오지 못했습니다.";
  }
}

function updateAddressFromMarker(kakao, position) {
  const requestId = ++markerMoveRequestId;
  const geocoder = new kakao.maps.services.Geocoder();

  mapMessage.value = "옮긴 마커의 주소를 확인하고 있습니다.";
  geocoder.coord2Address(
    position.getLng(),
    position.getLat(),
    (result, status) => {
      if (requestId !== markerMoveRequestId) return;

      if (status !== kakao.maps.services.Status.OK || !result.length) {
        mapMessage.value =
          "이 위치의 주소를 찾지 못했습니다. 주변 주소를 검색해 주세요.";
        return;
      }

      const address =
        result[0].road_address?.address_name ||
        result[0].address?.address_name;

      if (address) lastSeenPlace.value = address;
      mapMessage.value = "마커를 옮긴 위치로 마지막 목격 장소를 변경했습니다.";
    },
  );
}

function replaceMarker(kakao, position) {
  if (kakaoMarker) kakaoMarker.setMap(null);
  kakaoMarker = new kakao.maps.Marker({
    map: kakaoMap,
    position,
    draggable: true,
  });

  kakao.maps.event.addListener(kakaoMarker, "dragstart", () => {
    mapMessage.value = "마커를 원하는 목격 위치로 옮겨 주세요.";
  });
  kakao.maps.event.addListener(kakaoMarker, "dragend", () => {
    const movedPosition = kakaoMarker.getPosition();
    kakaoMap.setCenter(movedPosition);
    updateAddressFromMarker(kakao, movedPosition);
  });
  kakaoMap.setCenter(position);
}

async function showAddressOnMap(address) {
  if (!address.trim()) return;
  if (!KAKAO_MAP_APP_KEY) {
    mapMessage.value = "카카오맵에서 입력한 주소를 확인할 수 있습니다.";
    return;
  }

  try {
    const kakao = await loadKakaoMaps();
    const initialized = await initializeMap(
      kakao,
      new kakao.maps.LatLng(37.5665, 126.978),
    );
    if (!initialized) return;

    new kakao.maps.services.Geocoder().addressSearch(address, (result, status) => {
      if (status !== kakao.maps.services.Status.OK) {
        mapMessage.value = "정확한 도로명 또는 지번 주소를 입력해 주세요.";
        return;
      }

      replaceMarker(kakao, new kakao.maps.LatLng(result[0].y, result[0].x));
      mapMessage.value = "입력한 위치입니다. 마커를 직접 옮길 수도 있습니다.";
    });
  } catch {
    mapMessage.value =
      "지도를 불러오지 못했습니다. 카카오맵에서 주소를 확인해 주세요.";
  }
}

async function showPlaceOnMap(place) {
  if (!KAKAO_MAP_APP_KEY) {
    mapMessage.value = `선택한 장소: ${place.name} · 마커를 직접 옮길 수도 있습니다.`;
    return;
  }

  try {
    const kakao = await loadKakaoMaps();
    const position = new kakao.maps.LatLng(Number(place.y), Number(place.x));
    if (!(await initializeMap(kakao, position))) return;

    replaceMarker(kakao, position);
    mapMessage.value =
      `선택한 장소: ${place.name} · 마커를 직접 옮길 수도 있습니다.`;
  } catch {
    mapMessage.value = "지도를 불러오지 못했습니다. 주소를 확인해 주세요.";
  }
}

function keywordSearch(services, query) {
  if (!kakaoPlaces) kakaoPlaces = new services.Places();
  return new Promise((resolve) => {
    kakaoPlaces.keywordSearch(query, (data, status) => {
      resolve(status === services.Status.OK ? data : []);
    });
  });
}

function addressSearch(services, query) {
  return new Promise((resolve) => {
    new services.Geocoder().addressSearch(query, (data, status) => {
      resolve(status === services.Status.OK ? data : []);
    });
  });
}

async function searchPlaceSuggestions(query) {
  const normalizedQuery = query.trim();
  if (
    isSelectingPlace.value ||
    !KAKAO_MAP_APP_KEY ||
    normalizedQuery.length < 2
  ) return;

  try {
    const requestId = ++placeSearchRequestId;
    latestPlaceQuery = normalizedQuery;
    const kakao = await loadKakaoMaps();
    const services = kakao.maps.services;
    const [placeResults, addressResults] = await Promise.all([
      keywordSearch(services, normalizedQuery),
      addressSearch(services, normalizedQuery),
    ]);

    if (
      isSelectingPlace.value ||
      requestId !== placeSearchRequestId ||
      latestPlaceQuery !== normalizedQuery
    ) return;

    const isAddressQuery =
      /(?:대로|로|길)\s*\d+/.test(normalizedQuery) ||
      /\d{1,4}(?:-\d{1,4})?/.test(normalizedQuery);
    const places = isAddressQuery ? [] : placeResults.slice(0, 5);
    const addresses =
      isAddressQuery || !placeResults.length ? addressResults.slice(0, 5) : [];

    if (isSelectingPlace.value) return;
    const suggestions = [
      ...places.map((place) => ({
        type: "place",
        id: `place-${place.id}`,
        name: place.place_name,
        address: place.road_address_name || place.address_name,
        roadAddress: place.road_address_name || "",
        jibunAddress: place.address_name || "",
        x: place.x,
        y: place.y,
      })),
      ...addresses.map((address) => ({
        type: "address",
        id: `address-${address.address_name}`,
        name: address.address_name,
        address: address.road_address?.address_name || address.address_name,
        roadAddress: address.road_address?.address_name || "",
        jibunAddress: address.address_name || "",
        x: address.x,
        y: address.y,
      })),
    ];
    const seen = new Set();

    placeSuggestions.value = suggestions.filter((suggestion) => {
      const key = `${suggestion.x}:${suggestion.y}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    suggestionsVisible.value = placeSuggestions.value.length > 0;
  } catch {
    if (!isSelectingPlace.value) {
      clearSuggestionState();
    }
  }
}

async function selectPlaceSuggestion(place) {
  isSelectingPlace.value = true;
  clearTimeout(placeSearchTimer);
  clearTimeout(mapSearchTimer);
  placeSearchRequestId += 1;

  const selectedValue =
    place.type === "place"
      ? place.name
      : place.roadAddress || place.address || place.jibunAddress || place.name;

  latestPlaceQuery = selectedValue;
  lastSeenPlace.value = selectedValue;
  clearSuggestionState();
  mapMessage.value = "";

  try {
    await nextTick();
    if (place.x && place.y) {
      await showPlaceOnMap(place);
    } else {
      await showAddressOnMap(selectedValue);
    }
  } finally {
    isSelectingPlace.value = false;
  }
}

function handleInput(value) {
  if (isSelectingPlace.value) return;

  lastSeenPlace.value = value;
  scheduleLocationSearch(value);
}

function scheduleLocationSearch(address) {
  if (isSelectingPlace.value) return;

  clearTimeout(mapSearchTimer);
  clearTimeout(placeSearchTimer);
  placeSearchRequestId += 1;

  const normalizedAddress = address.trim();
  latestPlaceQuery = normalizedAddress;
  mapMessage.value = "";
  clearSuggestionState();
  if (normalizedAddress.length < 2) {
    if (!normalizedAddress) showDefaultMap();
    return;
  }

  placeSearchTimer = setTimeout(() => {
    if (!isSelectingPlace.value && latestPlaceQuery === normalizedAddress) {
      searchPlaceSuggestions(normalizedAddress);
    }
  }, 220);

  mapSearchTimer = setTimeout(async () => {
    if (isSelectingPlace.value || latestPlaceQuery !== normalizedAddress) return;
    await nextTick();
    if (isSelectingPlace.value || latestPlaceQuery !== normalizedAddress) return;
    showAddressOnMap(normalizedAddress);
  }, 500);
}

function closePlaceSuggestions() {
  clearTimeout(placeSearchTimer);
  placeSearchRequestId += 1;
  clearSuggestionState();
}

onBeforeUnmount(() => {
  clearTimeout(placeSearchTimer);
  clearTimeout(mapSearchTimer);
  if (kakaoMarker) kakaoMarker.setMap(null);
});

onMounted(() => {
  const savedPlace = lastSeenPlace.value.trim();

  showDefaultMap();

  if (savedPlace.length >= 2) {
    scheduleLocationSearch(savedPlace);
  }
});

</script>

<template>
  <div class="location-field">
    <label>
      <span class="label-row"><span>마지막 목격 장소 <b>*</b></span></span>
      <input
        :value="lastSeenPlace"
        type="text"
        placeholder="장소명 또는 주소를 입력하세요"
        autocomplete="off"
        required
        @input="handleInput($event.target.value)"
        @keydown.esc="closePlaceSuggestions"
      />
    </label>

    <div
      v-if="suggestionsVisible && placeSuggestions.length"
      class="place-suggestions"
      role="listbox"
    >
      <button
        v-for="place in placeSuggestions"
        :key="place.id"
        type="button"
        class="place-suggestion"
        role="option"
        @mousedown.prevent
        @click.prevent.stop="selectPlaceSuggestion(place)"
      >
        <span class="place-suggestion-type">
          {{ place.type === "place" ? "장소" : "주소" }}
        </span>
        <span class="place-suggestion-copy">
          <strong>{{ place.name }}</strong>
          <small>{{ place.address }}</small>
        </span>
      </button>
    </div>
  </div>

  <div class="map-block">
    <div
      ref="mapContainer"
      class="kakao-map"
      :class="{ fallback: !KAKAO_MAP_APP_KEY }"
    >
      <div v-if="!KAKAO_MAP_APP_KEY" class="map-fallback-copy">
        <strong>Kakao Maps</strong>
        <span>{{ lastSeenPlace || "장소를 검색해 주세요" }}</span>
      </div>
    </div>
    <div class="map-meta">
      <span>{{ mapMessage || "지도를 준비하고 있습니다." }}</span>
      <a
        v-if="lastSeenPlace.trim()"
        :href="kakaoMapSearchUrl"
        target="_blank"
        rel="noopener noreferrer"
      >
        카카오맵에서 확인 ↗
      </a>
    </div>
  </div>
</template>
