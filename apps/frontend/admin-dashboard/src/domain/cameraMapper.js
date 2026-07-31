import { formatKstDateTime } from "./caseMapper";

const DEFAULT_MEDIA_STREAM_BASE_URL = "http://70.12.108.93:8888";

export function toUiCameraStatus(status) {
  const normalized = String(status ?? "").trim().toUpperCase();
  if (["ONLINE", "OFFLINE", "ERROR"].includes(normalized)) {
    return normalized.toLowerCase();
  }
  return normalized ? normalized.toLowerCase() : "offline";
}

export function mapCamera(source = {}) {
  return {
    id: source.id,
    cameraCode: source.cameraCode ?? "-",
    cameraName: source.cameraName ?? "-",
    mediaServerId: source.mediaServer?.id ?? null,
    mediaServerCode: source.mediaServer?.serverCode ?? "-",
    mediaServerName: source.mediaServer?.name ?? "-",
    latitude: source.latitude ?? "-",
    longitude: source.longitude ?? "-",
    address: source.address ?? "-",
    status: toUiCameraStatus(source.status),
    statusCode: source.status ?? "OFFLINE",
    lastHeartbeat: formatKstDateTime(source.lastHeartbeat) || "-",
    createdAt: formatKstDateTime(source.createdAt) || "-",
    updatedAt: formatKstDateTime(source.updatedAt) || "-"
  };
}

export function buildCameraPlaybackUrl(cameraCode, baseUrl) {
  const normalizedCode = String(cameraCode ?? "").trim();
  if (!normalizedCode) throw new TypeError("카메라 코드가 필요합니다.");

  const configuredBaseUrl = [
    baseUrl,
    import.meta.env.VITE_MEDIA_STREAM_BASE_URL,
    DEFAULT_MEDIA_STREAM_BASE_URL
  ].map((candidate) => String(candidate ?? "").trim())
    .find(Boolean)
    ?.replace(/\/+$/, "");
  if (!configuredBaseUrl) throw new TypeError("미디어 스트림 기본 URL이 필요합니다.");

  const query = new URLSearchParams({
    controls: "false",
    muted: "true",
    autoplay: "true",
    playsinline: "true",
    disablepictureinpicture: "true"
  });
  return `${configuredBaseUrl}/${encodeURIComponent(normalizedCode)}?${query}`;
}
