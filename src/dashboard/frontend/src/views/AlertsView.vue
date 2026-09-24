<script setup lang="ts">
import { computed, ref, watch } from "vue";
import {
  Bell,
  Search,
  CircleAlert,
  ChevronLeft,
  ChevronRight,
} from "lucide-vue-next";
import { useAlertStore } from "../stores/alertStore";
import { useMotorStore } from "../stores/motorStore";
import { alertLabel, alertStatus } from "../services/alerts";
import type { DiagnosisAlert } from "../types/alerts";
import "../styles/alerts.css";

const alerts = useAlertStore();
const motor = useMotorStore();
const query = ref("");
const filter = ref("all");
const page = ref(1);
const pageSize = 25;
const available = computed(
  () =>
    motor.connection === "connected" &&
    motor.system.validity === "valid" &&
    ["running", "finishing"].includes(motor.system.experimentStatus) &&
    motor.system.readerCaughtUp,
);
const status = (r: DiagnosisAlert) =>
  alertStatus(alerts.current, r, alerts.session, available.value);
const counts = computed(() => ({
  all: alerts.records.length,
  active: alerts.records.filter((r) => status(r) === "active").length,
  resolved: alerts.records.filter((r) => status(r) === "resolved").length,
  unread: alerts.records.filter((r) => !r.read).length,
  read: alerts.records.filter((r) => r.read).length,
}));
const filtered = computed(() => {
  const term = query.value.trim().toLowerCase();
  return alerts.records
    .filter(
      (r) =>
        (filter.value === "all" ||
          (filter.value === "active" && status(r) === "active") ||
          (filter.value === "resolved" && status(r) === "resolved") ||
          (filter.value === "unread" && !r.read) ||
          (filter.value === "read" && r.read)) &&
        [alertLabel(r.code), r.code, r.model, "ID", r.motorId, r.busId]
          .join(" ")
          .toLowerCase()
          .includes(term),
    )
    .slice()
    .sort((a, b) => b.startedAt - a.startedAt || b.id.localeCompare(a.id));
});
const totalPages = computed(() =>
  Math.max(1, Math.ceil(filtered.value.length / pageSize)),
);
const visible = computed(() =>
  filtered.value.slice((page.value - 1) * pageSize, page.value * pageSize),
);
watch([query, filter, () => motor.mode], () => {
  page.value = 1;
});
watch(totalPages, (n) => {
  page.value = Math.min(page.value, n);
});
function time(at: number | null | undefined) {
  if (at == null) return "—";
  return new Date(at).toLocaleString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}
</script>

<template>
  <div class="alerts-page">
    <header class="alerts-heading">
      <h2>알림</h2>
    </header>
    <div v-if="alerts.storageWarning" class="alerts-notice" role="status">
      알림 기록 오류
    </div>
    <div class="alerts-summary">
      <div>
        <span>전체 기록</span
        ><strong>{{ counts.all.toLocaleString() }}<small>건</small></strong>
      </div>
      <div class="danger">
        <span><i></i>발생 중</span
        ><strong>{{ counts.active.toLocaleString() }}<small>건</small></strong>
      </div>
      <div class="resolved">
        <span>해제됨</span
        ><strong
          >{{ counts.resolved.toLocaleString() }}<small>건</small></strong
        >
      </div>
      <div class="pending">
        <span>미확인</span
        ><strong>{{ counts.unread.toLocaleString() }}<small>건</small></strong>
      </div>
      <div class="success">
        <span>확인</span
        ><strong>{{ counts.read.toLocaleString() }}<small>건</small></strong>
      </div>
    </div>
    <section class="panel alerts-panel" aria-label="이상진단 알림 기록">
      <div class="alerts-toolbar">
        <div class="alerts-filters" role="group" aria-label="알림 필터">
          <button
            v-for="item in [
              { key: 'all', label: '전체' },
              { key: 'active', label: '발생 중' },
              { key: 'resolved', label: '해제됨' },
              { key: 'unread', label: '미확인' },
              { key: 'read', label: '확인' },
            ]"
            :key="item.key"
            :aria-pressed="filter === item.key"
            @click="filter = item.key"
          >
            {{ item.label }}
          </button>
        </div>
        <label class="alerts-search"
          ><Search :size="16" /><input
            v-model="query"
            type="search"
            aria-label="알림 검색"
            placeholder="이상 종류, 모터 또는 ID 검색"
        /></label>
      </div>
      <div class="alerts-list-heading" aria-hidden="true">
        <span>이상 종류 / 모터</span><span>확인 여부</span><span>발생 시각</span
        ><span>확인 시각</span>
      </div>
      <ol v-if="visible.length" class="alerts-list">
        <li
          v-for="record in visible"
          :key="record.id"
          class="alert-row"
          :data-status="record.read ? 'read' : 'unread'"
          :data-active="status(record) === 'active'"
          :data-read="record.read"
          :class="{ unread: !record.read }"
        >
          <button
            type="button"
            class="alert-read-target"
            :aria-label="
              alertLabel(record.code) +
              ' · ' +
              record.model +
              ' ID ' +
              record.motorId +
              ' · ' +
              time(record.startedAt) +
              (record.read ? ' · 확인됨' : ' · 알림 확인')
            "
            @click="alerts.markRead(record.id)"
          ></button>
          <div class="alert-identity">
            <span class="alert-icon"><CircleAlert :size="19" /></span>
            <div>
              <h3>
                {{ alertLabel(record.code) }}
                <span
                  v-if="status(record) === 'active'"
                  class="alert-read-state occurring"
                  >발생 중</span
                >
                <span
                  v-else-if="status(record) === 'resolved'"
                  class="alert-read-state resolved"
                  >해제됨</span
                >
              </h3>
              <p>
                {{ record.model }} <b>ID {{ record.motorId }}</b
                ><span v-if="record.busId"> · {{ record.busId }}</span>
              </p>
            </div>
          </div>
          <div>
            <span class="alert-state" :class="record.read ? 'read' : 'unread'"
              ><i></i>{{ record.read ? "확인" : "미확인" }}</span
            >
          </div>
          <div class="alert-time">
            <small>발생</small
            ><time :datetime="new Date(record.startedAt).toISOString()">{{
              time(record.startedAt)
            }}</time>
          </div>
          <div class="alert-time">
            <small>확인</small><time>{{ time(record.readAt) }}</time>
          </div>
        </li>
      </ol>
      <div v-else class="alerts-empty">
        <Bell :size="34" />
        <h3>
          {{
            alerts.records.length
              ? "조건에 맞는 알림이 없습니다"
              : "수신된 이상 알림이 없습니다"
          }}
        </h3>
      </div>
      <footer class="alerts-pagination">
        <span>총 {{ filtered.length.toLocaleString() }}건 · 최신 발생순</span>
        <div>
          <button
            aria-label="이전 알림 페이지"
            :disabled="page <= 1"
            @click="page--"
          >
            <ChevronLeft :size="16" /></button
          ><span>{{ page }} / {{ totalPages }}</span
          ><button
            aria-label="다음 알림 페이지"
            :disabled="page >= totalPages"
            @click="page++"
          >
            <ChevronRight :size="16" />
          </button>
        </div>
      </footer>
    </section>
  </div>
</template>
