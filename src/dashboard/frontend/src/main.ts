import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import router from "./router";
import "./styles/global.css";
const app = createApp(App).use(createPinia()).use(router);
void router.isReady().then(() => app.mount("#app"));
