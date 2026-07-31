import { createApp, nextTick } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const {
  createCameraMock,
  getCameraMock,
  listMediaServerOptionsMock,
  updateCameraNameMock,
  routerPushMock,
  routerBackMock,
  route
} = vi.hoisted(() => ({
  createCameraMock: vi.fn(),
  getCameraMock: vi.fn(),
  listMediaServerOptionsMock: vi.fn(),
  updateCameraNameMock: vi.fn(),
  routerPushMock: vi.fn(),
  routerBackMock: vi.fn(),
  route: { params: { cameraId: "7" } }
}));

vi.mock("../api/cameraApi", () => ({
  createCamera: createCameraMock,
  getCamera: getCameraMock,
  listMediaServerOptions: listMediaServerOptionsMock,
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

const mediaServerOptions = [
  { id: 3, serverCode: "media-a", name: "Media A" },
  { id: 8, serverCode: "media-b", name: "Media B" }
];

const deferred = () => {
  let resolve;
  const promise = new Promise((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
};

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

  const setField = (name, value) => {
    const element = root.querySelector(`[name="${name}"]`);
    element.value = String(value);
    element.dispatchEvent(new Event(element.tagName === "SELECT" ? "change" : "input", { bubbles: true }));
    return element;
  };

  const fillValidCreateForm = (overrides = {}) => {
    const values = {
      mediaServerId: 3,
      cameraCode: "camera-03",
      cameraName: "3번 카메라",
      latitude: 37.5,
      longitude: 127,
      address: "설치 주소",
      rtspUrl: "rtsp://camera-source/stream",
      ...overrides
    };
    Object.entries(values).forEach(([name, value]) => setField(name, value));
  };

  beforeEach(() => {
    createCameraMock.mockReset();
    getCameraMock.mockReset();
    listMediaServerOptionsMock.mockReset();
    updateCameraNameMock.mockReset();
    routerPushMock.mockReset();
    routerBackMock.mockReset();
    route.params.cameraId = "7";
    listMediaServerOptionsMock.mockResolvedValue(mediaServerOptions);
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

  it("loads Media Server options for a new camera and explains the MediaMTX path contract", async () => {
    route.params.cameraId = undefined;
    mount();
    await settle();

    expect(getCameraMock).not.toHaveBeenCalled();
    expect(listMediaServerOptionsMock).toHaveBeenCalledOnce();
    expect([...root.querySelectorAll('[name="mediaServerId"] option')].map((option) => option.textContent.trim())).toEqual([
      "Media Server 선택",
      "Media A (media-a)",
      "Media B (media-b)"
    ]);
    expect(root.textContent).toContain("MediaMTX 경로명과 대소문자까지 정확히 일치");
  });

  it("shows retry and empty states when Media Server options cannot be loaded", async () => {
    route.params.cameraId = undefined;
    listMediaServerOptionsMock
      .mockRejectedValueOnce(new Error("Media Server 조회 오류"))
      .mockResolvedValueOnce([]);
    mount();
    await settle();

    expect(root.textContent).toContain("Media Server 조회 오류");
    [...root.querySelectorAll("button")].find((button) => button.textContent.includes("다시 시도")).click();
    await settle();

    expect(listMediaServerOptionsMock).toHaveBeenCalledTimes(2);
    expect(root.textContent).toContain("등록 가능한 Media Server가 없습니다.");
    expect(root.querySelector('[name="cameraCode"]')).toBeNull();
  });

  it("validates required fields before registration", async () => {
    route.params.cameraId = undefined;
    mount();
    await settle();

    [...root.querySelectorAll("button")].find((button) => button.textContent.trim() === "CCTV 등록").click();
    await settle();

    expect(createCameraMock).not.toHaveBeenCalled();
    expect(root.textContent).toContain("Media Server를 선택해 주세요.");
    expect(root.textContent).toContain("CCTV 코드를 입력해 주세요.");
    expect(root.textContent).toContain("CCTV 이름을 입력해 주세요.");
    expect(root.textContent).toContain("위도를 입력해 주세요.");
    expect(root.textContent).toContain("경도를 입력해 주세요.");
    expect(root.textContent).toContain("설치 주소를 입력해 주세요.");
    expect(root.textContent).toContain("RTSP URL을 입력해 주세요.");
  });

  it("trims strings, accepts zero coordinates, sends numeric values, and prevents duplicate submits", async () => {
    route.params.cameraId = undefined;
    const request = deferred();
    createCameraMock.mockReturnValue(request.promise);
    mount();
    await settle();
    fillValidCreateForm({
      cameraCode: "  camera-03  ",
      cameraName: "  3번 카메라  ",
      latitude: 0,
      longitude: 0,
      address: "  설치 주소  ",
      rtspUrl: "  rtsp://camera-source/stream  "
    });

    const submitButton = [...root.querySelectorAll("button")]
      .find((button) => button.textContent.trim() === "CCTV 등록");
    submitButton.click();
    submitButton.click();
    await settle();

    expect(createCameraMock).toHaveBeenCalledOnce();
    expect(createCameraMock).toHaveBeenCalledWith({
      mediaServerId: 3,
      cameraCode: "camera-03",
      cameraName: "3번 카메라",
      latitude: 0,
      longitude: 0,
      address: "설치 주소",
      rtspUrl: "rtsp://camera-source/stream"
    });
    expect(submitButton.disabled).toBe(true);

    request.resolve({ id: 21, cameraCode: "camera-03", status: "OFFLINE" });
    await settle();
    expect(routerPushMock).toHaveBeenCalledWith("/admin/cameras/21/edit");
  });

  it("rejects overlong strings and out-of-range coordinates", async () => {
    route.params.cameraId = undefined;
    mount();
    await settle();
    fillValidCreateForm({
      cameraCode: "c".repeat(101),
      cameraName: "n".repeat(101),
      latitude: 90.1,
      longitude: -180.1,
      address: "a".repeat(256),
      rtspUrl: "r".repeat(501)
    });

    [...root.querySelectorAll("button")].find((button) => button.textContent.trim() === "CCTV 등록").click();
    await settle();

    expect(createCameraMock).not.toHaveBeenCalled();
    expect(root.textContent).toContain("CCTV 코드는 100자 이하");
    expect(root.textContent).toContain("CCTV 이름은 100자 이하");
    expect(root.textContent).toContain("위도는 -90 이상 90 이하");
    expect(root.textContent).toContain("경도는 -180 이상 180 이하");
    expect(root.textContent).toContain("설치 주소는 255자 이하");
    expect(root.textContent).toContain("RTSP URL은 500자 이하");
  });

  it("rejects camera codes that are unsafe as DB and MediaMTX path identifiers", async () => {
    route.params.cameraId = undefined;
    mount();
    await settle();
    fillValidCreateForm({ cameraCode: "front/gate" });

    [...root.querySelectorAll("button")].find((button) => button.textContent.trim() === "CCTV 등록").click();
    await settle();

    expect(createCameraMock).not.toHaveBeenCalled();
    expect(root.textContent).toContain("영문, 숫자, 마침표, 밑줄, 하이픈만 사용할 수 있습니다.");
  });

  it("maps a duplicate-resource response to the CCTV code field", async () => {
    route.params.cameraId = undefined;
    createCameraMock.mockRejectedValue({
      status: 409,
      code: "DUPLICATE_RESOURCE",
      message: "Camera code already exists."
    });
    mount();
    await settle();
    fillValidCreateForm();

    [...root.querySelectorAll("button")].find((button) => button.textContent.trim() === "CCTV 등록").click();
    await settle();

    expect(root.textContent).toContain("이미 등록된 CCTV 코드입니다.");
    expect(root.querySelector('[name="cameraCode"]').getAttribute("aria-invalid")).toBe("true");
    expect(root.querySelector(".camera-operation-error")).toBeNull();
  });

  it("reloads Media Server options after a not-found response while retaining other inputs", async () => {
    route.params.cameraId = undefined;
    listMediaServerOptionsMock
      .mockResolvedValueOnce(mediaServerOptions)
      .mockResolvedValueOnce([{ id: 9, serverCode: "media-new", name: "Media New" }]);
    createCameraMock.mockRejectedValue({
      status: 404,
      code: "RESOURCE_NOT_FOUND",
      message: "Media server was not found."
    });
    mount();
    await settle();
    fillValidCreateForm();

    [...root.querySelectorAll("button")].find((button) => button.textContent.trim() === "CCTV 등록").click();
    await settle();

    expect(listMediaServerOptionsMock).toHaveBeenCalledTimes(2);
    expect(root.querySelector('[name="mediaServerId"]').value).toBe("");
    expect(root.textContent).toContain("선택한 Media Server를 찾을 수 없습니다.");
    expect(root.querySelector('[name="cameraCode"]').value).toBe("camera-03");
    expect(root.querySelector('[name="address"]').value).toBe("설치 주소");
    expect(root.textContent).toContain("Media New (media-new)");
  });

  it("shows an unclassified create error without clearing the entered values", async () => {
    route.params.cameraId = undefined;
    createCameraMock.mockRejectedValue({ status: 500, code: "INTERNAL_ERROR", message: "등록 API 오류" });
    mount();
    await settle();
    fillValidCreateForm();

    [...root.querySelectorAll("button")].find((button) => button.textContent.trim() === "CCTV 등록").click();
    await settle();

    expect(root.textContent).toContain("등록 API 오류");
    expect(root.querySelector('[name="cameraName"]').value).toBe("3번 카메라");
    expect(routerPushMock).not.toHaveBeenCalled();
  });
});
