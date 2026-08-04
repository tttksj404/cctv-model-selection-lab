import { afterEach, describe, expect, it, vi } from "vitest";
import { buildCameraPlaybackUrl, mapCamera, toUiCameraStatus } from "./cameraMapper";

describe("cameraMapper", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("maps backend camera metadata without inventing unavailable values", () => {
    expect(mapCamera({
      id: 1,
      cameraCode: "camera-01",
      cameraName: "Camera 01",
      mediaServer: { id: 3, serverCode: "rpi5-media-01", name: "RPI5" },
      latitude: 0,
      longitude: 0,
      address: "설치 위치 미정",
      status: "OFFLINE",
      lastHeartbeat: null,
      createdAt: "2026-07-30T00:00:00Z"
    })).toMatchObject({
      id: 1,
      cameraCode: "camera-01",
      cameraName: "Camera 01",
      mediaServerCode: "rpi5-media-01",
      latitude: 0,
      longitude: 0,
      status: "offline",
      lastHeartbeat: "-",
      createdAt: "2026-07-30 09:00"
    });
  });

  it("normalizes supported DB statuses", () => {
    expect(toUiCameraStatus("ONLINE")).toBe("online");
    expect(toUiCameraStatus("offline")).toBe("offline");
    expect(toUiCameraStatus("ERROR")).toBe("error");
  });

  it("builds an encoded MediaMTX HLS playlist URL from the environment base and camera code", () => {
    const url = new URL(buildCameraPlaybackUrl("camera/01", "http://media.example:8888/"));
    expect(url.origin).toBe("http://media.example:8888");
    expect(url.pathname).toBe("/camera%2F01/index.m3u8");
    expect(url.search).toBe("");
  });

  it("builds a same-origin proxy URL without a duplicate slash", () => {
    const url = new URL(
      buildCameraPlaybackUrl("camera/01", "/media-stream/"),
      "https://admin-dev.example.com"
    );

    expect(url.origin).toBe("https://admin-dev.example.com");
    expect(url.pathname).toBe("/media-stream/camera%2F01/index.m3u8");
    expect(url.search).toBe("");
  });

  it("falls back to the default media URL when the environment value is blank", () => {
    vi.stubEnv("VITE_MEDIA_STREAM_BASE_URL", "   ");

    const url = new URL(buildCameraPlaybackUrl("camera-01"));

    expect(url.origin).toBe("http://70.12.108.93:8888");
    expect(url.pathname).toBe("/camera-01/index.m3u8");
  });

  it("rejects missing camera codes", () => {
    expect(() => buildCameraPlaybackUrl("", "http://media.example")).toThrow("카메라 코드");
  });
});
