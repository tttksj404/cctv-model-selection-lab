import { defineStore } from "pinia";
import { login as loginApi } from "../api/mockApi";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: sessionStorage.getItem("accessToken") || "",
    user: JSON.parse(sessionStorage.getItem("user") || "null")
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.token)
  },
  actions: {
    async login(credentials) {
      const result = await loginApi(credentials);
      this.token = result.accessToken;
      this.user = result.user;
      sessionStorage.setItem("accessToken", result.accessToken);
      sessionStorage.setItem("user", JSON.stringify(result.user));
    },
    logout() {
      this.token = "";
      this.user = null;
      sessionStorage.clear();
    }
  }
});
