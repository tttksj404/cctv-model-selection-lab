import { apiClient, unwrapData, unwrapPagedData } from "./httpClient";

const cameraPath = (cameraId, suffix = "") =>
  `/admin/cameras/${encodeURIComponent(cameraId)}${suffix}`;

export async function listCameras(params = {}) {
  return unwrapPagedData(await apiClient.get("/admin/cameras", { params }));
}

export async function getCamera(cameraId) {
  return unwrapData(await apiClient.get(cameraPath(cameraId)));
}

export async function updateCameraName(cameraId, cameraName) {
  return unwrapData(await apiClient.patch(cameraPath(cameraId, "/name"), { cameraName }));
}
