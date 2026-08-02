import client from "./httpClient";

const candidateCache = new Map();

function requestKey(params) {
  return Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => `${key}=${String(value)}`)
    .join("&");
}

export async function fetchAdminCandidates(params = {}) {
  const key = requestKey(params);
  const cached = candidateCache.get(key);
  const response = await client.get("/admin/candidates", {
    params,
    headers: cached?.etag ? { "If-None-Match": cached.etag } : undefined,
    validateStatus: (status) => (status >= 200 && status < 300) || status === 304
  });

  if (response.status === 304 && cached) return cached.result;

  const data = response.data || {};
  const result = { rows: data.data || [], meta: data.meta || {} };
  const etag = response.headers?.etag;
  if (etag) candidateCache.set(key, { etag, result });
  return result;
}

export async function fetchAdminCandidate(candidateId) {
  const { data } = await client.get(`/admin/candidates/${candidateId}`);
  return data.data;
}

export async function reviewAdminCandidate(candidateId, payload) {
  const { data } = await client.patch(`/admin/candidates/${candidateId}/review`, payload);
  return data.data;
}

export function objectUrl(objectKey) {
  if (!objectKey) return "";
  const base = import.meta.env.VITE_STORAGE_PUBLIC_URL;
  return base ? `${base.replace(/\/$/, "")}/${objectKey}` : "";
}
