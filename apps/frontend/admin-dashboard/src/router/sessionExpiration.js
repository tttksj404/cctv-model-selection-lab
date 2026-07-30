export const createSessionExpirationHandler = ({ auth, router }) => (error) => {
  if (!auth.isAuthenticated || error?.status !== 401) return;

  const currentRoute = router.currentRoute.value;
  auth.expireSession();

  if (currentRoute.path === "/login") return;

  return router.replace({
    path: "/login",
    query: {
      redirect: currentRoute.fullPath,
      reason: error.code === "SESSION_EXPIRED" ? "session-expired" : "authentication-required"
    }
  }).catch(() => {});
};
