import { createRouter, createWebHistory } from "vue-router";
import TrendsView from "../views/TrendsView.vue";
import MotorsView from "../views/MotorsView.vue";
import OverviewView from "../views/OverviewView.vue";
import AlertsView from "../views/AlertsView.vue";
import PlaceholderView from "../views/PlaceholderView.vue";
export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", component: OverviewView },
    { path: "/motors", component: MotorsView },
    { path: "/overview", redirect: "/" },
    { path: "/trends", component: TrendsView },
    { path: "/alerts", component: AlertsView },
    ...["logs", "settings"].map((name) => ({
      path: "/" + name,
      component: PlaceholderView,
      meta: { title: name.charAt(0).toUpperCase() + name.slice(1) },
    })),
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});
