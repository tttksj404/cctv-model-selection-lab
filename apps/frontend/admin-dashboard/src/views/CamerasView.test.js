import { createApp, nextTick } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { listCamerasMock, mapCameraMock, routerPushMock } = vi.hoisted(() => ({
  listCamerasMock: vi.fn(),
  mapCameraMock: vi.fn(),
  routerPushMock: vi.fn()
}));

vi.mock("../api/cameraApi", () => ({ listCameras: listCamerasMock }));
vi.mock("../domain/cameraMapper", () => ({ mapCamera: mapCameraMock }));
vi.mock("vue-router", () => ({ useRouter: () => ({ push: routerPushMock }) }));

import CamerasView from "./CamerasView.vue";

const camera = (overrides = {}) => ({
  id: 1,
  cameraCode: "camera-01",
  cameraName: "Camera 01",
  address: "설치 위치 미정",
  latitude: 0,
  longitude: 0,
  mediaServerCode: "rpi5-media-01",
  mediaServerName: "RPI5 Media",
  status: "offline",
  lastHeartbeat: "-",
  ...overrides
});

const result = (data = [], meta = {}) => ({
  data,
  meta: {
    page: 0,
    size: 10,
    totalElements: data.length,
    totalPages: data.length ? 1 : 0,
    sort: "cameraCode,asc",
    ...meta
  }
});

const deferred = () => {
  let resolve;
  const promise = new Promise((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
};

const settle = async () => {
  for (let index = 0; index < 5; index += 1) {
    await Promise.resolve();
    await nextTick();
  }
};

describe("CamerasView", () => {
  let app;
  let root;

  const mount = () => {
    root = document.createElement("div");
    document.body.appendChild(root);
    app = createApp(CamerasView);
    app.mount(root);
  };

  beforeEach(() => {
    mapCameraMock.mockImplementation((item) => item);
  });

  afterEach(() => {
    app?.unmount();
    root?.remove();
  });

  it("uses server pagination and renders real camera metadata", async () => {
    listCamerasMock.mockResolvedValue(result([camera()], { totalElements: 14, totalPages: 2 }));
    mount();
    await settle();

    expect(listCamerasMock).toHaveBeenCalledWith({
      status: undefined,
      search: undefined,
      page: 0,
      size: 10,
      sort: "cameraCode,asc"
    });
    expect(root.textContent).toContain("camera-01");
    expect(root.textContent).toContain("RPI5 Media");
    expect(root.textContent).toContain("전체 14건");
    const registerButton = root.querySelector(".section-heading button");
    expect(registerButton.disabled).toBe(false);
    registerButton.click();
    expect(routerPushMock).toHaveBeenCalledWith("/admin/cameras/new");
  });

  it("converts status and search filters to backend parameters", async () => {
    listCamerasMock.mockResolvedValue(result([camera()]));
    mount();
    await settle();

    const search = root.querySelector('input[placeholder="카메라 코드 또는 이름"]');
    search.value = "camera-04";
    search.dispatchEvent(new Event("input", { bubbles: true }));
    await settle();

    const status = root.querySelector("select");
    status.value = "offline";
    status.dispatchEvent(new Event("change", { bubbles: true }));
    await settle();

    expect(listCamerasMock).toHaveBeenLastCalledWith({
      status: "OFFLINE",
      search: "camera-04",
      page: 0,
      size: 10,
      sort: "cameraCode,asc"
    });
  });

  it("ignores an older response that completes after a newer filter request", async () => {
    const oldRequest = deferred();
    listCamerasMock
      .mockImplementationOnce(() => oldRequest.promise)
      .mockResolvedValueOnce(result([camera({ cameraCode: "camera-new" })]));
    mount();

    const status = root.querySelector("select");
    status.value = "error";
    status.dispatchEvent(new Event("change", { bubbles: true }));
    await settle();
    expect(root.textContent).toContain("camera-new");

    oldRequest.resolve(result([camera({ cameraCode: "camera-stale" })]));
    await settle();
    expect(root.textContent).not.toContain("camera-stale");
  });

  it("shows an error and retries the list request", async () => {
    listCamerasMock
      .mockRejectedValueOnce(new Error("카메라 조회 오류"))
      .mockResolvedValueOnce(result([camera()]));
    mount();
    await settle();

    expect(root.textContent).toContain("카메라 조회 오류");
    [...root.querySelectorAll("button")].find((button) => button.textContent.includes("다시 시도")).click();
    await settle();

    expect(listCamerasMock).toHaveBeenCalledTimes(2);
    expect(root.textContent).toContain("camera-01");
  });
});
