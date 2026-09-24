import { createRouter, createWebHistory } from "vue-router";
import TrendsView from "../views/TrendsView.vue";
import MotorsView from "../views/MotorsView.vue";
import OverviewView from "../views/OverviewView.vue";
import AlertsView from "../views/AlertsView.vue";
import PlaceholderView from "../views/PlaceholderView.vue";
import ControlView from "../views/ControlView.vue";
import LogsView from "../views/LogsView.vue";
export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", component: OverviewView },
    { path: "/control", component: ControlView },
    { path: "/logs", component: LogsView },
    { path: "/logs/:runId", component: TrendsView },
    { path: "/motors", component: MotorsView },
    { path: "/overview", redirect: "/" },
    { path: "/trends", component: TrendsView },
    { path: "/alerts", component: AlertsView },
    ...["settings"].map((name) => ({
      path: "/" + name,
      component: PlaceholderView,
      meta: { title: name.charAt(0).toUpperCase() + name.slice(1) },
    })),
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});
