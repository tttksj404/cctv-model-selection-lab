export const runtimeConfig = Object.freeze({
  dataSource: "mock",
  integrationStatus: "disabled",
  allowNetworkRequests: false,
  allowJetsonDispatch: false,
});

export function assertOfflineRuntime(config = runtimeConfig) {
  if (
    config.dataSource !== "mock" ||
    config.integrationStatus !== "disabled" ||
    config.allowNetworkRequests ||
    config.allowJetsonDispatch
  ) {
    throw new Error("현재 대시보드는 mock-only 실행만 허용합니다.");
  }
}

