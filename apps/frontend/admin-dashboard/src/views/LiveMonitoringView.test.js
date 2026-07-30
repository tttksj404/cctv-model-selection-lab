import { createApp, nextTick } from "vue";
import { afterEach, describe, expect, it, vi } from "vitest";

const { listCamerasMock } = vi.hoisted(() => ({ listCamerasMock: vi.fn() }));
vi.mock("../api/cameraApi", () => ({ listCameras: listCamerasMock }));

import LiveMonitoringView from "./LiveMonitoringView.vue";

const rawCamera = (id, code) => ({
  id,
  cameraCode: code,
  cameraName: `Camera ${String(id).padStart(2, "0")}`,
  mediaServer: { id: 3, serverCode: "rpi5-media-01", name: "RPI5 Media" },
  latitude: 0,
  longitude: 0,
  address: "설치 위치 미정",
  status: "OFFLINE",
  lastHeartbeat: null,
  createdAt: "2026-07-30T00:00:00Z",
  updatedAt: "2026-07-30T00:00:00Z"
});

const result = (data) => ({
  data,
  meta: { page: 0, size: 4, totalElements: data.length, totalPages: 1, sort: "cameraCode,asc" }
});

const settle = async () => {
  for (let index = 0; index < 6; index += 1) {
    await Promise.resolve();
    await nextTick();
  }
};

describe("LiveMonitoringView", () => {
  let app;
  let root;

  const mount = () => {
    root = document.createElement("div");
    document.body.appendChild(root);
    app = createApp(LiveMonitoringView);
    app.mount(root);
  };

  afterEach(() => {
    app?.unmount();
    root?.remove();
  });

  it("loads up to four cameras and fills the remaining quad slots", async () => {
    listCamerasMock.mockResolvedValue(result([
      rawCamera(1, "camera-01"),
      rawCamera(2, "camera-02")
    ]));
    mount();
    await settle();

    expect(listCamerasMock).toHaveBeenCalledWith({ page: 0, size: 4, sort: "cameraCode,asc" });
    expect(root.querySelectorAll(".live-stream-card")).toHaveLength(4);
    expect(root.querySelectorAll(".empty-camera-slot")).toHaveLength(2);
    const iframeSources = [...root.querySelectorAll("iframe")].map((iframe) => iframe.src);
    expect(iframeSources[0]).toContain("/camera-01?");
    expect(iframeSources[1]).toContain("/camera-02?");
  });

  it("shows API DB status separately from player state", async () => {
    listCamerasMock.mockResolvedValue(result([rawCamera(1, "camera-01")]));
    mount();
    await settle();

    root.querySelector('button[aria-label="카메라 정보"]').click();
    await settle();

    expect(root.textContent).toContain("DB 상태");
    expect(root.textContent).toContain("OFFLINE");
    expect(root.textContent).toContain("재생 상태");
  });

  it("keeps the quad UI and retries after a camera-list error", async () => {
    listCamerasMock
      .mockRejectedValueOnce(new Error("CCTV API 오류"))
      .mockResolvedValueOnce(result([rawCamera(1, "camera-01")]));
    mount();
    await settle();

    expect(root.textContent).toContain("CCTV API 오류");
    expect(root.querySelectorAll(".live-stream-card")).toHaveLength(4);
    root.querySelector(".live-monitoring-notice button").click();
    await settle();

    expect(listCamerasMock).toHaveBeenCalledTimes(2);
    expect(root.textContent).toContain("Camera 01");
  });
});
