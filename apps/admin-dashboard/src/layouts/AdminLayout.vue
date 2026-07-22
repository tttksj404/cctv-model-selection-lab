<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  Bell,
  BellRing,
  ClipboardList,
  FileSearch,
  Folder,
  History,
  MapPinned,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Radar,
  Route,
  Settings,
  UserCog,
  Video
} from "lucide-vue-next";
import { adminMenu } from "../router";
import { getNotifications } from "../api/mockApi";
import { useAuthStore } from "../stores/auth";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const collapsed = ref(false);
const mobileOpen = ref(false);
const dropdownOpen = ref(false);
const notifications = ref([]);
const clockString = ref("");
let clockTimer = null;
const title = computed(() => route.meta.title || "관리자");
const unread = computed(() => notifications.value.filter((item) => item.unread).length);

const menuIcons = {
  "/admin/dashboard": Folder,
  "/admin/cases": ClipboardList,
  "/admin/live-monitoring": Video,
  "/admin/recording-search": FileSearch,
  "/admin/candidates": Radar,
  "/admin/routes": Route,
  "/admin/cameras": MapPinned,
  "/admin/users": UserCog,
  "/admin/logs": History,
  "/admin/notifications": BellRing,
  "/admin/settings": Settings
};

const iconFor = (path) => menuIcons[path] || Folder;
const go = (path) => {
  router.push(path);
  mobileOpen.value = false;
};
const logout = () => {
  auth.logout();
  router.push("/login");
};
const closeDropdown = (event) => {
  if (!event.target.closest(".notification-wrap")) dropdownOpen.value = false;
};
const updateClock = () => {
  clockString.value = new Intl.DateTimeFormat("ko-KR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "Asia/Seoul"
  }).format(new Date()) + " KST";
};

onMounted(async () => {
  notifications.value = await getNotifications();
  updateClock();
  clockTimer = window.setInterval(updateClock, 1000);
  console.table({
    innerWidth: window.innerWidth,
    innerHeight: window.innerHeight,
    outerWidth: window.outerWidth,
    outerHeight: window.outerHeight,
    devicePixelRatio: window.devicePixelRatio
  });
  document.addEventListener("click", closeDropdown);
});

onUnmounted(() => {
  document.removeEventListener("click", closeDropdown);
  if (clockTimer) window.clearInterval(clockTimer);
});
</script>

<template>
  <div :class="['app-layout', 'app-shell', collapsed && 'is-collapsed']">
    <div v-if="mobileOpen" class="sidebar-backdrop" @click="mobileOpen = false" />
    <aside :class="['app-sidebar', 'sidebar', collapsed && 'collapsed', mobileOpen && 'mobile-open']">
      <div class="brand html-brand">
        <div class="brand-main">
          <button v-if="collapsed" class="brand-collapsed-trigger" @click="collapsed = false" aria-label="사이드바 펼치기">
            <span class="brand-mark"><img src="/logo.png" alt="Eyes For U" /></span>
            <span class="brand-hover-icon"><PanelLeftOpen :size="18" /></span>
            <span class="sidebar-tooltip">사이드바 열기</span>
          </button>
          <div v-else>
            <span class="brand-logo-row"><img src="/logo.png" alt="Eyes For U" /></span>
            <span>Eyes For U</span>
            <strong>관제실 대시보드</strong>
          </div>
        </div>
        <button v-if="!collapsed" class="sidebar-toggle" @click="collapsed = true" aria-label="사이드바 접기">
          <PanelLeftClose :size="18" />
        </button>
      </div>

      <nav>
        <button
          v-for="item in adminMenu"
          :key="item.path"
          :class="{ active: route.path.startsWith(item.path) }"
          :title="collapsed ? item.label : undefined"
          @click="go(item.path)"
        >
          <span class="menu-symbol">
            <component :is="iconFor(item.path)" :size="22" :stroke-width="2" />
          </span>
          <span v-if="!collapsed">{{ item.label }}</span>
        </button>
      </nav>

      <div v-if="!collapsed" class="sidebar-version">v0.2 · Vue MVP</div>
    </aside>

    <main class="app-main">
      <button class="mobile-sidebar-button" @click="mobileOpen = true">
        <Menu :size="16" />
        메뉴
      </button>

      <header class="header">
        <div class="header-title">{{ title }}</div>
        <div class="header-actions">
          <div class="system-online"><span />SYSTEM ONLINE</div>
          <div class="clock-text">{{ clockString }}</div>
          <div class="header-divider" />
          <div class="operator-name">관제자 김민준</div>
          <div class="notification-wrap">
            <button class="icon-button" @click.stop="dropdownOpen = !dropdownOpen" aria-label="알림">
              <Bell :size="18" />
              <span v-if="unread" class="badge-count">{{ unread }}</span>
            </button>
            <section v-if="dropdownOpen" class="notification-panel">
              <div class="panel-title">알림</div>
              <button
                v-for="item in notifications"
                :key="item.id"
                :class="['notification-item', item.unread && 'unread']"
                @click="go(item.route)"
              >
                <strong>{{ item.title }}</strong>
                <p>{{ item.message }}</p>
              </button>
            </section>
          </div>
          <button class="logout-button" @click="logout">로그아웃</button>
        </div>
      </header>

      <div class="page-container">
        <RouterView />
      </div>
    </main>
  </div>
</template>
