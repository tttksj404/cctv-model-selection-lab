const DEFAULT_CAMERA_POLL_INTERVAL_MS = 10_000;
const configuredInterval = Number(import.meta.env.VITE_CAMERA_POLL_INTERVAL_MS);

export const CAMERA_POLL_INTERVAL_MS = Number.isFinite(configuredInterval) && configuredInterval > 0
  ? configuredInterval
  : DEFAULT_CAMERA_POLL_INTERVAL_MS;
