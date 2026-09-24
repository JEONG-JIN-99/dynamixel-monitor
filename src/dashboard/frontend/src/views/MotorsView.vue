<script setup lang="ts">
import { computed, ref, shallowRef, watch } from "vue";
import {
  Search,
  ExternalLink,
  Pause,
  Play,
  Activity,
  RefreshCw,
  ChevronDown,
  CircleAlert,
} from "lucide-vue-next";
import { useOverview } from "../composables/useOverview";
import { motorKey, SCREEN_INTERVAL_MS } from "../services/overview";
import {
  controlTable,
  registerRows,
  manualUrl,
  supportedModels,
} from "../services/controlTable";
import type { Area } from "../services/controlTable";
import type { Sample, MotorMetadata } from "../types/motor";
import "../styles/motors.css";
const { store, options, selectedKey, selectedMotor, latest } = useOverview();
const tab = ref<"all" | Area>("all");
const query = ref("");
const order = ref("asc");
const selectedAddress = ref(126);
const paused = ref(false);
const frozen = shallowRef<{
  sample: Sample | null;
  metadata: MotorMetadata | undefined;
}>();
const metadata = computed(() =>
  store.metadata.find((m) => motorKey(m) === selectedKey.value),
);
const modelSupported = computed(
  () =>
    !selectedMotor.value || supportedModels.includes(selectedMotor.value.model),
);
const tabs = [
  { key: "all", label: "전체", count: 53 },
  { key: "EEPROM", label: "EEPROM", count: 22 },
  { key: "RAM", label: "RAM", count: 31 },
] as const;
const rows = computed(() =>
  modelSupported.value
    ? registerRows(
        paused.value ? (frozen.value?.sample ?? null) : latest.value,
        paused.value ? frozen.value?.metadata : metadata.value,
      )
    : [],
);
const filtered = computed(() => {
  const text = query.value.trim().toLowerCase();
  return rows.value
    .filter(
      (row) =>
        (tab.value === "all" || row.area === tab.value) &&
        (!text ||
          `${row.address} ${row.name} ${row.english}`
            .toLowerCase()
            .includes(text)),
    )
    .sort((a, b) =>
      order.value === "asc" ? a.address - b.address : b.address - a.address,
    );
});
const selected = computed(
  () =>
    filtered.value.find((row) => row.address === selectedAddress.value) ??
    filtered.value[0],
);
const receivedCount = computed(
  () => rows.value.filter((row) => row.value !== "—").length,
);
const interval = computed(() => {
  const seconds =
    store.experiment?.sampleIntervalSec ??
    (store.system.configuredHz ? 1 / store.system.configuredHz : null);
  return seconds && seconds > 0 ? `${Number(seconds.toFixed(4))}초` : "—";
});
const notice = computed(() => {
  if (!modelSupported.value)
    return "현재 모터는 이 표의 대상이 아닙니다. XM430-W210과 XM430-W350의 53개 항목을 지원합니다.";
  if (paused.value)
    return "화면 표시를 일시정지했습니다. 데이터 수집은 계속됩니다.";
  if (store.mode === "mock")
    return store.connection === "connected"
      ? ""
      : "가상 데이터 서버 연결 대기 중입니다. 마지막 수신값을 표시합니다.";
  if (store.system.error) return store.system.error;
  if (store.connection !== "connected")
    return "서버 연결 대기 중입니다. 마지막 수신값이 있으면 유지합니다.";
  if (!latest.value)
    return "측정 데이터 수신 대기 중입니다.";
  if (!store.live)
    return "마지막 수신 기록을 표시합니다. 현재 모터 상태와 다를 수 있습니다.";
  return "";
});
function togglePause() {
  if (!paused.value)
    frozen.value = { sample: latest.value, metadata: metadata.value };
  paused.value = !paused.value;
}
watch(
  () => [selectedKey.value, store.mode, store.experiment?.runId],
  () => {
    paused.value = false;
    frozen.value = undefined;
  },
);
const isReceived = (status: string) =>
  ["수신", "변환값 수신", "메타데이터", "명령 기록"].includes(status);
function rowTime(value: number | null) {
  return value == null
    ? "시각 정보 없음"
    : new Date(value).toLocaleString("ko-KR", { hour12: false });
}
</script>
<template>
  <div class="motors-page">
    <div class="motors-heading">
      <div>
        <h2>모터</h2>
      </div>
      <a
        :href="manualUrl(selectedMotor?.model ?? '')"
        target="_blank"
        rel="noreferrer"
        class="manual-link"
        >공식 문서 <ExternalLink :size="15"
      /></a>
    </div>
    <section class="panel register-toolbar" aria-label="모터 선택 및 갱신 정보">
      <div class="register-motor-select">
        <label for="register-motor">모터종류</label>
        <div class="select-wrap">
          <select
            id="register-motor"
            v-model="selectedKey"
            :disabled="!options.length"
          >
            <option v-if="!options.length" value="">수신된 모터 없음</option>
            <option
              v-for="motor in options"
              :key="motorKey(motor)"
              :value="motorKey(motor)"
            >
              {{ motor.model }} · ID {{ motor.id }}
            </option></select
          ><ChevronDown :size="17" />
        </div>
      </div>
      <div class="register-timing">
        <span
          ><Activity :size="17" />데이터 수집 주기
          <strong>{{ interval }}</strong></span
        ><span
          ><RefreshCw :size="16" />화면 갱신
          <strong>{{ SCREEN_INTERVAL_MS / 1000 }}초</strong></span
        >
      </div>
    </section>
    <div v-if="notice" class="notice register-notice" role="status">
      <CircleAlert :size="16" />{{ notice }}
    </div>
    <div class="register-summary">
      <strong>전체 {{ controlTable.length }}개 항목</strong
      ><span>EEPROM 22개 · RAM 31개</span
      ><span class="provided-count"
        >값 제공 {{ receivedCount }} / {{ rows.length }}개</span
      >
    </div>
    <div class="register-tabs" role="group" aria-label="메모리 영역 선택">
      <button
        v-for="item in tabs"
        :key="item.key"
        :aria-pressed="tab === item.key"
        @click="tab = item.key"
      >
        {{ item.label }} <span>{{ item.count }}</span>
      </button>
    </div>
    <section class="panel register-panel" aria-label="모터 주소 데이터 표">
      <div class="register-filters">
        <label class="register-search"
          ><Search :size="18" /><input
            v-model="query"
            type="search"
            placeholder="주소 또는 항목명 검색"
            aria-label="주소 또는 항목명 검색"
        /></label>
        <div class="register-actions">
          <select v-model="order" aria-label="주소 정렬">
            <option value="asc">주소순 ↑</option>
            <option value="desc">주소순 ↓</option></select
          ><button :aria-pressed="paused" @click="togglePause">
            <component :is="paused ? Play : Pause" :size="16" />{{
              paused ? "화면 재개" : "화면 일시정지"
            }}
          </button>
        </div>
      </div>
      <div
        class="register-scroll"
        tabindex="0"
        aria-label="주소 데이터 표 스크롤"
      >
        <table class="register-table">
          <caption class="sr-only">
            {{
              selectedMotor?.model ?? "XM430-W210 / W350"
            }}
            공식 Control Table 53개 항목. 값이 없는 항목은 미수신입니다.
          </caption>
          <thead>
            <tr>
              <th scope="col">주소</th>
              <th scope="col">항목명</th>
              <th scope="col">크기</th>
              <th scope="col">접근</th>
              <th scope="col">원시값</th>
              <th scope="col">변환값</th>
              <th scope="col">단위</th>
              <th scope="col">수신 상태</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in filtered"
              :key="row.address"
              :data-address="row.address"
              :class="{ selected: selected?.address === row.address }"
              @click="selectedAddress = row.address"
            >
              <td class="address-cell">{{ row.address }}</td>
              <th scope="row">
                <button
                  class="register-name"
                  :aria-pressed="selected?.address === row.address"
                  @click="selectedAddress = row.address"
                >
                  {{ row.name }}<small>{{ row.english }}</small>
                </button>
              </th>
              <td>{{ row.size }} B</td>
              <td>
                <span class="access-pill">{{ row.access }}</span>
              </td>
              <td class="register-raw numeric">{{ row.rawText }}</td>
              <td class="register-value numeric">{{ row.value }}</td>
              <td>{{ row.displayUnit }}</td>
              <td>
                <span
                  class="register-status"
                  :class="{
                    received: isReceived(row.status),
                    error: row.status === '읽기 오류',
                  }"
                  :title="rowTime(row.receivedAt)"
                  ><i class="dot"></i>{{ row.status }}</span
                >
              </td>
            </tr>
            <tr v-if="!filtered.length">
              <td colspan="8" class="register-empty">
                {{
                  modelSupported
                    ? "검색 조건에 맞는 항목이 없습니다."
                    : "지원 모델의 데이터를 선택하세요."
                }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="register-detail" aria-live="polite">
        <div v-if="selected">
          <strong>{{ selected.name }} · 주소 {{ selected.address }}</strong
          ><span>{{ selected.detail }}</span
          >
        </div>
        <span class="register-row-count"
          >표시 {{ filtered.length }} /
          {{ tab === "all" ? 53 : tab === "EEPROM" ? 22 : 31 }}개</span
        >
      </div>
    </section>
    <div class="register-footnotes">
      <p>R: 읽기 전용 · RW: 읽기/쓰기 가능</p>
    </div>
  </div>
</template>
