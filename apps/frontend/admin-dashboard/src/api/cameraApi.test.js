import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  createCamera,
  getCamera,
  listCameras,
  listMediaServerOptions,
  updateCameraName
} from "./cameraApi";
import { apiClient, setUnauthorizedHandler } from "./httpClient";

const originalAdapter = apiClient.defaults.adapter;
const response = (config, data, status = 200) => ({
  config,
  data,
  headers: {},
  request: {},
  status,
  statusText: "OK"
});

describe("cameraApi", () => {
  beforeEach(() => {
    document.cookie = "XSRF-TOKEN=camera-api-token; path=/";
    setUnauthorizedHandler(null);
  });

  afterEach(() => {
    apiClient.defaults.adapter = originalAdapter;
    document.cookie = "XSRF-TOKEN=; Max-Age=0; path=/";
    setUnauthorizedHandler(null);
  });

  it("returns camera page data and forwards server paging filters", async () => {
    const adapter = vi.fn(async (config) => response(config, {
      data: [{ id: 1, cameraCode: "camera-01" }],
      meta: { page: 0, size: 10, totalElements: 1, totalPages: 1, sort: "cameraCode,asc" }
    }));
    apiClient.defaults.adapter = adapter;

    await expect(listCameras({ status: "OFFLINE", page: 0, size: 10 })).resolves.toMatchObject({
      data: [{ id: 1, cameraCode: "camera-01" }],
      meta: { totalElements: 1 }
    });
    expect(adapter.mock.calls[0][0]).toMatchObject({
      method: "get",
      url: "/admin/cameras",
      params: { status: "OFFLINE", page: 0, size: 10 }
    });
  });

  it("unwraps camera detail and sends name-only PATCH", async () => {
    const adapter = vi.fn(async (config) => response(config, {
      data: {
        id: 7,
        cameraCode: "camera-07",
        cameraName: config.method === "patch" ? "변경 이름" : "기존 이름"
      }
    }));
    apiClient.defaults.adapter = adapter;

    await expect(getCamera(7)).resolves.toMatchObject({ cameraName: "기존 이름" });
    await expect(updateCameraName(7, "변경 이름")).resolves.toMatchObject({ cameraName: "변경 이름" });

    expect(adapter.mock.calls.map(([config]) => `${config.method} ${config.url}`)).toEqual([
      "get /admin/cameras/7",
      "patch /admin/cameras/7/name"
    ]);
    expect(JSON.parse(adapter.mock.calls[1][0].data)).toEqual({ cameraName: "변경 이름" });
  });

  it("unwraps the safe Media Server option list", async () => {
    const adapter = vi.fn(async (config) => response(config, {
      data: [
        { id: 3, serverCode: "media-a", name: "Media A" },
        { id: 8, serverCode: "media-b", name: "Media B" }
      ]
    }));
    apiClient.defaults.adapter = adapter;

    await expect(listMediaServerOptions()).resolves.toEqual([
      { id: 3, serverCode: "media-a", name: "Media A" },
      { id: 8, serverCode: "media-b", name: "Media B" }
    ]);
    expect(adapter).toHaveBeenCalledOnce();
    expect(adapter.mock.calls[0][0]).toMatchObject({
      method: "get",
      url: "/admin/media-servers/options"
    });
  });

  it("posts exactly the seven camera registration fields and unwraps the created camera", async () => {
    const payload = {
      mediaServerId: 3,
      cameraCode: "camera-03",
      cameraName: "3번 카메라",
      latitude: 37.5,
      longitude: 127,
      address: "설치 주소",
      rtspUrl: "rtsp://camera-source/stream"
    };
    const adapter = vi.fn(async (config) => response(config, {
      data: { id: 13, cameraCode: "camera-03", status: "OFFLINE" }
    }, 201));
    apiClient.defaults.adapter = adapter;

    await expect(createCamera(payload)).resolves.toMatchObject({
      id: 13,
      cameraCode: "camera-03",
      status: "OFFLINE"
    });
    expect(adapter).toHaveBeenCalledOnce();
    expect(adapter.mock.calls[0][0]).toMatchObject({ method: "post", url: "/admin/cameras" });
    expect(JSON.parse(adapter.mock.calls[0][0].data)).toEqual(payload);
  });
});
