<script setup lang="ts">
import {
  Cpu,
  House,
  SlidersHorizontal,
  ChartNoAxesCombined,
  Bell,
  Logs,
} from "lucide-vue-next";
import { useAlertStore } from "../../stores/alertStore";
const alerts = useAlertStore();
const links = [
  { path: "/", title: "개요", icon: House },
  { path: "/control", title: "제어", icon: SlidersHorizontal },
  { path: "/motors", title: "모터", icon: Cpu },
  { path: "/trends", title: "상세 분석", icon: ChartNoAxesCombined },
  { path: "/alerts", title: "알림", icon: Bell },
  { path: "/logs", title: "로그", icon: Logs },
];
</script>
<template>
  <aside class="sidebar">
    <div class="brand"><Cpu :size="29" /><span>모터 대시보드</span></div>
    <nav aria-label="주 메뉴">
      <RouterLink
        v-for="link in links"
        :key="link.path"
        :to="{
          path: link.path,
          query: ['mock', 'csv'].includes(String($route.query.source))
            ? { source: $route.query.source }
            : {},
        }"
        :class="{
          active:
            $route.path === link.path ||
            (link.path === '/logs' && $route.path.startsWith('/logs/')),
        }"
        :aria-label="link.title"
      >
        <component :is="link.icon" :size="23" /><span>{{ link.title }}</span>
        <span
          v-if="link.path === '/alerts' && alerts.unreadCount"
          class="alert-badge"
          :aria-label="'읽지 않은 알림 ' + alerts.unreadCount + '개'"
          role="status"
          >{{ alerts.unreadCount > 99 ? "99+" : alerts.unreadCount }}</span
        >
      </RouterLink>
    </nav>
  </aside>
</template>

<style scoped>
.sidebar nav a {
  position: relative;
}
.sidebar .alert-badge {
  margin-left: auto;
  padding: 2px 6px;
  min-width: 21px;
  border-radius: 10px;
  background: #e46e80;
  color: #190d16;
  font-size: 11px;
  line-height: 17px;
  font-weight: 750;
  text-align: center;
}
@media (max-width: 1000px) {
  .sidebar .alert-badge {
    display: inline-block;
    position: absolute;
    top: 2px;
    right: 2px;
    margin: 0;
    min-width: 17px;
    padding: 0 4px;
    font-size: 9px;
  }
}
</style>
