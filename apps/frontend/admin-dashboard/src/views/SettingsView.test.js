import { createPinia, setActivePinia } from "pinia";
import { createApp } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";

const routerPushMock = vi.hoisted(() => vi.fn());
vi.mock("vue-router", () => ({ useRouter: () => ({ push: routerPushMock }) }));

import { useAuthStore } from "../stores/auth";
import SettingsView from "./SettingsView.vue";

describe("SettingsView", () => {
  let app;
  let root;

  const mount = (role) => {
    const pinia = createPinia();
    setActivePinia(pinia);
    const auth = useAuthStore();
    auth.user = { id: 1, loginId: "admin", name: "관리자", role };
    auth.initialized = true;

    root = document.createElement("div");
    document.body.appendChild(root);
    app = createApp(SettingsView);
    app.use(pinia);
    app.mount(root);
  };

  afterEach(() => {
    app?.unmount();
    root?.remove();
  });

  it("일반 관리자에게 관리자 계정 관리 바로가기를 숨긴다", () => {
    mount("ADMIN");
    expect(root.textContent).not.toContain("관리자 계정 관리");
  });

  it("최고 관리자에게 관리자 계정 관리 바로가기를 표시한다", () => {
    mount("SUPER_ADMIN");
    expect(root.textContent).toContain("관리자 계정 관리");
  });
});
