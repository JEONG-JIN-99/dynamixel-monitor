<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import {
  Bell,
  CheckCheck,
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
    motor.system.experimentStatus === "running" &&
    motor.system.readerCaughtUp,
);
const status = (r: DiagnosisAlert) =>
  alertStatus(alerts.current, r, alerts.session, available.value);
const statusLabels = {
  active: "발생 중",
  resolved: "해제됨",
  unknown: "상태 확인 대기",
};
const counts = computed(() => ({
  all: alerts.records.length,
  active: alerts.records.filter((r) => status(r) === "active").length,
  resolved: alerts.records.filter((r) => status(r) === "resolved").length,
  unknown: alerts.records.filter((r) => status(r) === "unknown").length,
}));
const filtered = computed(() => {
  const term = query.value.trim().toLowerCase();
  return alerts.records
    .filter(
      (r) =>
        (filter.value === "all" || status(r) === filter.value) &&
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
function visibility() {
  alerts.setViewing(document.visibilityState === "visible");
}
onMounted(() => {
  visibility();
  document.addEventListener("visibilitychange", visibility);
});
onUnmounted(() => {
  alerts.setViewing(false);
  document.removeEventListener("visibilitychange", visibility);
});
function time(at: number | null) {
  if (at === null) return "—";
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
      <div>
        <span class="alerts-eyebrow">모터 상태 모니터링</span>
        <h2>알림</h2>
        <p>이상 발생부터 해제까지, 모터별 진단 기록을 확인하세요.</p>
      </div>
      <span class="alerts-read-note"
        ><CheckCheck :size="17" />이 페이지에서 알림이 읽음 처리됩니다</span
      >
    </header>
    <div v-if="motor.mode === 'mock'" class="alerts-notice demo">
      가상 데이터 알림 · 실제 모터의 기록과 별도로 표시합니다.
    </div>
    <div v-else-if="alerts.storageWarning" class="alerts-notice" role="status">
      {{ alerts.storageWarning }}
    </div>
    <div v-if="!available" class="alerts-notice" role="status">
      {{
        motor.connection !== "connected"
          ? "데이터 서버 연결 대기 중입니다."
          : "현재 진단 상태를 확인하고 있습니다."
      }}
      기존 알림은 유지하며, 진단이 확인되지 않은 이상은 해제하지 않습니다.
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
      <div class="pending">
        <span>상태 확인 대기</span
        ><strong>{{ counts.unknown.toLocaleString() }}<small>건</small></strong>
      </div>
      <div class="success">
        <span>해제됨</span
        ><strong
          >{{ counts.resolved.toLocaleString() }}<small>건</small></strong
        >
      </div>
    </div>
    <section class="panel alerts-panel" aria-label="이상진단 알림 기록">
      <div class="alerts-toolbar">
        <div class="alerts-filters" role="group" aria-label="알림 상태 필터">
          <button
            v-for="item in [
              { key: 'all', label: '전체' },
              { key: 'active', label: '발생 중' },
              { key: 'unknown', label: '확인 대기' },
              { key: 'resolved', label: '해제됨' },
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
        <span>이상 종류 / 모터</span><span>상태</span><span>발생 시각</span
        ><span>마지막 이상 확인 / 해제 시각</span>
      </div>
      <ol v-if="visible.length" class="alerts-list">
        <li
          v-for="record in visible"
          :key="record.id"
          class="alert-row"
          :data-status="status(record)"
        >
          <div class="alert-identity">
            <span class="alert-icon"><CircleAlert :size="19" /></span>
            <div>
              <h3>{{ alertLabel(record.code) }}</h3>
              <p>
                {{ record.model }} <b>ID {{ record.motorId }}</b
                ><span v-if="record.busId"> · {{ record.busId }}</span>
              </p>
            </div>
          </div>
          <div>
            <span class="alert-state" :class="status(record)"
              ><i></i>{{ statusLabels[status(record)] }}</span
            >
          </div>
          <div class="alert-time">
            <small>발생</small
            ><time :datetime="new Date(record.startedAt).toISOString()">{{
              time(record.startedAt)
            }}</time>
          </div>
          <div class="alert-time">
            <small>{{
              record.resolvedAt === null ? "마지막 이상 확인" : "해제"
            }}</small
            ><time>{{ time(record.resolvedAt ?? record.lastSeenAt) }}</time>
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
        <p>
          {{
            alerts.records.length
              ? "검색어나 상태 필터를 변경해 보세요."
              : "백엔드에서 이상진단 결과가 도착하면 여기에 기록됩니다."
          }}
        </p>
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
    <p class="alerts-footnote">
      읽음 처리는 이상 해제와 별개입니다.
      {{
        motor.mode === "mock"
          ? "가상 데이터 기록은 시연을 다시 시작하면 초기화됩니다."
          : "수신한 기록과 읽음 상태는 이 브라우저에 저장됩니다."
      }}
    </p>
  </div>
</template>
