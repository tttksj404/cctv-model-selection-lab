export function createLatestRequestRunner({ loadScenario, onPendingChange, onError }) {
  let latestRequestId = 0;

  return async function runLatest(key, onSuccess) {
    const requestId = ++latestRequestId;
    onPendingChange(true);

    try {
      const response = await loadScenario(key);
      if (requestId !== latestRequestId) {
        return false;
      }
      onSuccess(response);
      return true;
    } catch (error) {
      if (requestId === latestRequestId) {
        onError(error);
      }
      return false;
    } finally {
      if (requestId === latestRequestId) {
        onPendingChange(false);
      }
    }
  };
}

