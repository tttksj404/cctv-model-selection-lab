import { createPinia } from "pinia";
import { createApp } from "vue";
import App from "./App.vue";
import { setUnauthorizedHandler } from "./api/httpClient";
import { router } from "./router";
import { createSessionExpirationHandler } from "./router/sessionExpiration";
import { useAuthStore } from "./stores/auth";
import "./styles.css";

const pinia = createPinia();
const auth = useAuthStore(pinia);

setUnauthorizedHandler(createSessionExpirationHandler({ auth, router }));

createApp(App).use(pinia).use(router).mount("#root");
