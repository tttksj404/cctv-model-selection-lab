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
    const redirect = safeAdminRedirect(to.query.redirect);
    if (!auth.isSuperAdmin && redirect.split("?")[0] === "/admin/users") {
      return "/admin/dashboard";
    }
    return redirect;
  }

  if (!to.meta.public && !auth.isAuthenticated) {
    return { path: "/login", query: { redirect: to.fullPath } };
  }

  if (to.meta.requiresSuperAdmin && !auth.isSuperAdmin) {
    return "/admin/dashboard";
  }
};
