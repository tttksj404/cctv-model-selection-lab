import { describe, expect, it } from "vitest";
import { buildCameraPlaybackUrl, mapCamera, toUiCameraStatus } from "./cameraMapper";

describe("cameraMapper", () => {
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

  it("builds an encoded MediaMTX player URL from the environment base and camera code", () => {
    const url = new URL(buildCameraPlaybackUrl("camera/01", "http://media.example:8888/"));
    expect(url.origin).toBe("http://media.example:8888");
    expect(url.pathname).toBe("/camera%2F01");
    expect(url.searchParams.get("autoplay")).toBe("true");
    expect(url.searchParams.get("controls")).toBe("false");
    expect(url.searchParams.get("playsinline")).toBe("true");
  });

  it("rejects missing camera codes", () => {
    expect(() => buildCameraPlaybackUrl("", "http://media.example")).toThrow("카메라 코드");
  });
});
