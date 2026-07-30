import axios from "axios";

const API_BASE_URL = "/api/v1";
const CSRF_COOKIE_NAME = "XSRF-TOKEN";
const CSRF_HEADER_NAME = "X-XSRF-TOKEN";
const UNSAFE_METHODS = new Set(["post", "put", "patch", "delete"]);

let csrfRequestPromise = null;
let unauthorizedHandler = null;

export class ApiClientError extends Error {
  constructor({ message, status = null, code = "UNKNOWN_ERROR", timestamp = null, payload = null, cause } = {}) {
    super(message || "요청을 처리하지 못했습니다.", cause ? { cause } : undefined);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.timestamp = timestamp;
    this.payload = payload;
  }
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  withXSRFToken: true,
  xsrfCookieName: CSRF_COOKIE_NAME,
  xsrfHeaderName: CSRF_HEADER_NAME,
  headers: {
    Accept: "application/json"
  }
});

function readCookie(name) {
  if (typeof document === "undefined" || !document.cookie) return null;

  const encodedName = `${encodeURIComponent(name)}=`;
  const cookie = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(encodedName));

  if (!cookie) return null;

  try {
    return decodeURIComponent(cookie.slice(encodedName.length));
  } catch {
    return cookie.slice(encodedName.length);
  }
}

function responseEnvelope(responseOrEnvelope) {
  const looksLikeAxiosResponse = Boolean(
    responseOrEnvelope
      && typeof responseOrEnvelope === "object"
      && typeof responseOrEnvelope.status === "number"
      && "config" in responseOrEnvelope
      && "headers" in responseOrEnvelope
  );

  return looksLikeAxiosResponse ? responseOrEnvelope.data : responseOrEnvelope;
}

function invalidResponseError() {
  return new ApiClientError({
    code: "INVALID_API_RESPONSE",
    message: "서버 응답 형식이 올바르지 않습니다."
  });
}

export function unwrapData(responseOrEnvelope) {
  if (responseOrEnvelope?.status === 204) return undefined;

  const envelope = responseEnvelope(responseOrEnvelope);
  if (!envelope || typeof envelope !== "object" || !Object.hasOwn(envelope, "data")) {
    throw invalidResponseError();
  }
  return envelope.data;
}

export function unwrapPagedData(responseOrEnvelope) {
  const envelope = responseEnvelope(responseOrEnvelope);
  if (
    !envelope
      || typeof envelope !== "object"
      || !Object.hasOwn(envelope, "data")
      || !envelope.meta
      || typeof envelope.meta !== "object"
  ) {
    throw invalidResponseError();
  }

  return { data: envelope.data, meta: envelope.meta };
}

export function setUnauthorizedHandler(handler) {
  if (handler !== null && typeof handler !== "function") {
    throw new TypeError("Unauthorized handler must be a function or null.");
  }
  unauthorizedHandler = handler;
}

export async function issueCsrfToken(options = {}) {
  const force = typeof options === "boolean" ? options : Boolean(options.force);
  const existingToken = readCookie(CSRF_COOKIE_NAME);
  if (!force && existingToken) return existingToken;

  if (!csrfRequestPromise) {
    csrfRequestPromise = apiClient
      .get("/auth/csrf", { skipCsrfBootstrap: true })
      .then(() => {
        const token = readCookie(CSRF_COOKIE_NAME);
        if (!token) {
          throw new ApiClientError({
            code: "CSRF_TOKEN_MISSING",
            message: "보안 토큰을 발급받지 못했습니다."
          });
        }
        return token;
      })
      .finally(() => {
        csrfRequestPromise = null;
      });
  }

  return csrfRequestPromise;
}

apiClient.interceptors.request.use(async (config) => {
  const method = String(config.method || "get").toLowerCase();
  if (
    UNSAFE_METHODS.has(method)
      && !config.skipCsrfBootstrap
      && !readCookie(CSRF_COOKIE_NAME)
  ) {
    await issueCsrfToken();
  }
  return config;
});

function normalizeError(error) {
  if (error instanceof ApiClientError) return error;

  const payload = error?.response?.data;
  const status = Number.isInteger(payload?.status)
    ? payload.status
    : error?.response?.status ?? null;
  const code = typeof payload?.code === "string" && payload.code
    ? payload.code
    : status
      ? `HTTP_${status}`
      : error?.code === "ERR_CANCELED"
        ? "REQUEST_CANCELLED"
        : "NETWORK_ERROR";
  const message = typeof payload?.message === "string" && payload.message
    ? payload.message
    : status
      ? "요청을 처리하지 못했습니다."
      : error?.code === "ERR_CANCELED"
        ? "요청이 취소되었습니다."
        : "서버에 연결할 수 없습니다.";

  return new ApiClientError({
    message,
    status,
    code,
    timestamp: typeof payload?.timestamp === "string" ? payload.timestamp : null,
    payload: payload ?? null,
    cause: error
  });
}

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const normalizedError = normalizeError(error);
    if (
      normalizedError.status === 401
        && error?.config?.skipUnauthorizedHandler !== true
        && unauthorizedHandler
    ) {
      try {
        const handlerResult = unauthorizedHandler(normalizedError);
        if (handlerResult && typeof handlerResult.catch === "function") {
          handlerResult.catch(() => {});
        }
      } catch {
        // A navigation/session cleanup failure must not replace the API error.
      }
    }
    return Promise.reject(normalizedError);
  }
);
