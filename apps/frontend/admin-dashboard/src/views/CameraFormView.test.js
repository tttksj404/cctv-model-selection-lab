import { createApp, nextTick } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { getCameraMock, updateCameraNameMock, routerPushMock, routerBackMock, route } = vi.hoisted(() => ({
  getCameraMock: vi.fn(),
  updateCameraNameMock: vi.fn(),
  routerPushMock: vi.fn(),
  routerBackMock: vi.fn(),
  route: { params: { cameraId: "7" } }
}));

vi.mock("../api/cameraApi", () => ({
  getCamera: getCameraMock,
  updateCameraName: updateCameraNameMock
}));
vi.mock("vue-router", () => ({
  useRoute: () => route,
  useRouter: () => ({ push: routerPushMock, back: routerBackMock })
}));
vi.mock("../components/LiveStreamPlayer.vue", () => ({
  default: { props: ["protocol", "url"], emits: ["state-change"], render: () => null }
}));

import CameraFormView from "./CameraFormView.vue";

const rawCamera = (overrides = {}) => ({
  id: 7,
  cameraCode: "camera-07",
  cameraName: "Camera 07",
  mediaServer: { id: 3, serverCode: "rpi5-media-01", name: "RPI5 Media" },
  latitude: 0,
  longitude: 0,
  address: "설치 위치 미정",
  status: "OFFLINE",
  lastHeartbeat: null,
  createdAt: "2026-07-30T00:00:00Z",
  updatedAt: "2026-07-30T00:00:00Z",
  ...overrides
});

const settle = async () => {
  for (let index = 0; index < 6; index += 1) {
    await Promise.resolve();
    await nextTick();
  }
};

describe("CameraFormView", () => {
  let app;
  let root;

  const mount = () => {
    root = document.createElement("div");
    document.body.appendChild(root);
    app = createApp(CameraFormView);
    app.mount(root);
  };

  beforeEach(() => {
    route.params.cameraId = "7";
    routerPushMock.mockResolvedValue(undefined);
  });

  afterEach(() => {
    app?.unmount();
    root?.remove();
  });

  it("hydrates camera detail while keeping non-name fields read-only", async () => {
    getCameraMock.mockResolvedValue(rawCamera());
    mount();
    await settle();

    expect(getCameraMock).toHaveBeenCalledWith("7");
    const readonlyValues = [...root.querySelectorAll("input[disabled]")].map((input) => input.value);
    expect(readonlyValues).toContain("camera-07");
    expect(readonlyValues).toContain("RPI5 Media (rpi5-media-01)");
    expect(readonlyValues.length).toBeGreaterThanOrEqual(5);
    expect(root.querySelector("input:not([disabled])").value).toBe("Camera 07");
  });

  it("sends only a changed name and prevents duplicate saves", async () => {
    let resolveUpdate;
    updateCameraNameMock.mockImplementation(() => new Promise((resolve) => { resolveUpdate = resolve; }));
    getCameraMock.mockResolvedValue(rawCamera());
    mount();
    await settle();

    const nameInput = root.querySelector("input:not([disabled])");
    nameInput.value = "Renamed Camera";
    nameInput.dispatchEvent(new Event("input", { bubbles: true }));
    const saveButton = [...root.querySelectorAll("button")].find((button) => button.textContent.includes("이름 저장"));
    saveButton.click();
    saveButton.click();
    await settle();

    expect(updateCameraNameMock).toHaveBeenCalledOnce();
    expect(updateCameraNameMock).toHaveBeenCalledWith("7", "Renamed Camera");
    expect(saveButton.disabled).toBe(true);

    resolveUpdate(rawCamera({ cameraName: "Renamed Camera" }));
    await settle();
    expect(routerPushMock).toHaveBeenCalledWith("/admin/cameras");
  });

  it("does not PATCH when the name is unchanged", async () => {
    getCameraMock.mockResolvedValue(rawCamera());
    mount();
    await settle();

    [...root.querySelectorAll("button")].find((button) => button.textContent.includes("이름 저장")).click();
    await settle();

    expect(updateCameraNameMock).not.toHaveBeenCalled();
    expect(routerPushMock).toHaveBeenCalledWith("/admin/cameras");
  });

  it("shows a dedicated not-found state", async () => {
    getCameraMock.mockRejectedValue({ status: 404, message: "not found" });
    mount();
    await settle();
    expect(root.textContent).toContain("존재하지 않는 CCTV");
  });

  it("keeps direct new-camera access disabled without calling the API", async () => {
    route.params.cameraId = undefined;
    mount();
    await settle();
    expect(getCameraMock).not.toHaveBeenCalled();
    expect(root.textContent).toContain("신규 CCTV 등록은 현재 비활성화");
  });
});
