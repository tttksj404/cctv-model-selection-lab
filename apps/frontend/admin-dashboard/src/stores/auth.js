import { defineStore } from "pinia";
import { getCurrentAdmin, login as loginApi, logout as logoutApi } from "../api/authApi";

let bootstrapPromise = null;

export const useAuthStore = defineStore("auth", {
  state: () => ({
    user: null,
    initialized: false
  }),
  getters: {
    isAuthenticated: (state) => Boolean(state.user)
  },
  actions: {
    bootstrap() {
      if (this.initialized) return Promise.resolve(this.user);
      if (bootstrapPromise) return bootstrapPromise;

      bootstrapPromise = getCurrentAdmin()
        .then((user) => {
          this.user = user;
          this.initialized = true;
          return user;
        })
        .catch((error) => {
          const status = error?.response?.status ?? error?.status;
          if (status === 401) {
            this.user = null;
            this.initialized = true;
            return null;
          }

          this.initialized = false;
          throw error;
        })
        .finally(() => {
          bootstrapPromise = null;
        });

      return bootstrapPromise;
    },
    async login(credentials) {
      const user = await loginApi(credentials);
      this.user = user;
      this.initialized = true;
      return user;
    },
    async logout() {
      try {
        await logoutApi();
      } catch (error) {
        const status = error?.response?.status ?? error?.status;
        if (status !== 401) throw error;
      }

      this.expireSession();
    },
    expireSession() {
      this.user = null;
      this.initialized = true;
    }
  }
});
