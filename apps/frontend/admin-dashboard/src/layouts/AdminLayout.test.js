import { createPinia, setActivePinia } from "pinia";
import { createApp, nextTick } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";

const { getNotificationsMock, routerPushMock } = vi.hoisted(() => ({
  getNotificationsMock: vi.fn().mockResolvedValue([]),
  routerPushMock: vi.fn()
}));

vi.mock("../api/mockApi", () => ({ getNotifications: getNotificationsMock }));
vi.mock("vue-router", () => ({
  useRoute: () => ({ path: "/admin/dashboard", meta: { title: "대시보드" } }),
  useRouter: () => ({ push: routerPushMock, replace: vi.fn() })
}));
vi.mock("../router", () => ({
  adminMenu: [
    { path: "/admin/dashboard", label: "대시보드" },
    { path: "/admin/cameras", label: "CCTV 관리" },
    { path: "/admin/users", label: "관리자 계정", requiresSuperAdmin: true },
    { path: "/admin/settings", label: "설정" }
  ]
}));

import { useAuthStore } from "../stores/auth";
import AdminLayout from "./AdminLayout.vue";

describe("AdminLayout", () => {
  let app;
  let root;

  const mount = async (role) => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const auth = useAuthStore();
    auth.user = { id: 1, loginId: "admin", name: "관리자", role };
    auth.initialized = true;

    root = document.createElement("div");
    document.body.appendChild(root);
    app = createApp(AdminLayout);
    app.use(pinia);
    app.mount(root);
    await Promise.resolve();
    await nextTick();
    return auth;
  };

  afterEach(() => {
    app?.unmount();
    root?.remove();
  });

  it("일반 관리자의 사이드바에서 관리자 계정 메뉴를 숨긴다", async () => {
    await mount("ADMIN");
    expect(root.querySelector(".sidebar-submenu").textContent).not.toContain("관리자 계정");
  });

  it("최고 관리자의 사이드바에 관리자 계정 메뉴를 표시한다", async () => {
    await mount("SUPER_ADMIN");
    expect(root.querySelector(".sidebar-submenu").textContent).toContain("관리자 계정");
  });

  it("인증 store의 이름이 바뀌면 헤더 관리자 이름을 즉시 갱신한다", async () => {
    const auth = await mount("ADMIN");

    auth.user = { ...auth.user, name: "변경된 관리자" };
    await nextTick();

    expect(root.querySelector(".operator-name").textContent).toContain("변경된 관리자");
  });
});
