import { useAuthStore } from "../stores/auth";

export const safeAdminRedirect = (value) => {
  const redirect = Array.isArray(value) ? value[0] : value;
  if (typeof redirect !== "string") return "/admin/dashboard";
  return redirect === "/admin" || redirect.startsWith("/admin/") ? redirect : "/admin/dashboard";
};

export const authGuard = async (to) => {
  const auth = useAuthStore();
  document.title = `${to.meta.title || "관리자"} | Eyes On U`;

  if (!to.meta.skipAuthBootstrap) {
    try {
      await auth.bootstrap();
    } catch {
      if (!to.meta.public) {
        return {
          path: "/login",
          query: { redirect: to.fullPath, reason: "server-unavailable" }
        };
      }
    }
  }

  if (to.path === "/login" && auth.isAuthenticated) {
    return safeAdminRedirect(to.query.redirect);
  }

  if (!to.meta.public && !auth.isAuthenticated) {
    return { path: "/login", query: { redirect: to.fullPath } };
  }
};
