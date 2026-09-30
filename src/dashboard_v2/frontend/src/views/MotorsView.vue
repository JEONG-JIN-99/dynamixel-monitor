<script setup lang="ts">
import { computed, ref, shallowRef, watch } from "vue";
import {
  Search,
  ExternalLink,
  Pause,
  Play,
  Activity,
  RefreshCw,
  CircleAlert,
} from "lucide-vue-next";
import { useOverview } from "../composables/useOverview";
import { motorKey, SCREEN_INTERVAL_MS } from "../services/overview";
import {
  controlTable,
  registerCategories,
  registerRows,
  manualUrl,
  supportedModels,
} from "../services/controlTable";
import type { RegisterCategory } from "../services/controlTable";
import type { Sample, MotorMetadata } from "../types/motor";
import "../styles/motors.css";
import MotorSelector from "../components/MotorSelector.vue";
const { store, selectedKey, selectedMotor, latest } = useOverview();
const tab = ref<"all" | RegisterCategory>("status");
const query = ref("");
const order = ref("recommended");
const selectedAddress = ref(132);
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
  ...registerCategories.map(({ key, label, title, addresses }) => ({
    key,
    label,
    title,
    count: addresses.length,
  })),
  {
    key: "all" as const,
    label: "전체",
    title: "수집 대상 전체 항목",
    count: controlTable.length,
  },
];
const searchText = computed(() => query.value.trim().toLowerCase());
const activeTab = computed(() => (searchText.value ? "all" : tab.value));
const category = computed(() =>
  registerCategories.find((item) => item.key === activeTab.value),
);
const visibleTotal = computed(
  () => category.value?.addresses.length ?? controlTable.length,
);
const recommendedOrder = new Map<number, number>(
  registerCategories
    .flatMap((item) => [...item.addresses])
    .map((address, index) => [address, index]),
);
function selectCategory(key: "all" | RegisterCategory) {
  query.value = "";
  tab.value = key;
}
const rows = computed(() =>
  modelSupported.value
    ? registerRows(
        paused.value ? (frozen.value?.sample ?? null) : latest.value,
        paused.value ? frozen.value?.metadata : metadata.value,
      )
    : [],
);
const filtered = computed(() => {
  const addresses: readonly number[] | undefined = category.value?.addresses;
  return rows.value
    .filter(
      (row) =>
        (!addresses || addresses.includes(row.address)) &&
        (!searchText.value ||
          `${row.address} ${row.name} ${row.english}`
            .toLowerCase()
            .includes(searchText.value)),
    )
    .sort((a, b) =>
      order.value === "recommended"
        ? (recommendedOrder.get(a.address) ?? a.address) -
          (recommendedOrder.get(b.address) ?? b.address)
        : order.value === "asc"
          ? a.address - b.address
          : b.address - a.address,
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
      : "연결 대기 · 마지막 수신값 표시";
  if (store.system.error) return store.system.error;
  if (store.connection !== "connected")
    return "서버 연결 대기 중입니다. 마지막 수신값이 있으면 유지합니다.";
  if (!latest.value) return "측정 데이터 수신 대기 중입니다.";
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
        <MotorSelector select />
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
      ><span class="provided-count"
        >값 제공 {{ receivedCount }} / {{ rows.length }}개</span
      >
    </div>
    <div class="register-tabs" role="group" aria-label="항목 분류 선택">
      <button
        v-for="item in tabs"
        :key="item.key"
        :title="item.title"
        :aria-pressed="activeTab === item.key"
        @click="selectCategory(item.key)"
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
            placeholder="전체 항목에서 주소 또는 항목명 검색"
            aria-label="주소 또는 항목명 검색"
        /></label>
        <div class="register-actions">
          <select v-model="order" aria-label="항목 정렬">
            <option value="recommended">추천순</option>
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
            Control Table 수집 대상 53개 항목. 값이 없는 항목은 미수신입니다.
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
          <strong
            >{{ selected.name }} · 주소 {{ selected.address }} ·
            {{ selected.area }}</strong
          ><span>{{ selected.detail }}</span>
        </div>
        <span class="register-row-count"
          >표시 {{ filtered.length }} / {{ visibleTotal }}개</span
        >
      </div>
    </section>
    <div class="register-footnotes">
      <p>R: 읽기 전용 · RW: 읽기/쓰기 가능</p>
    </div>
  </div>
</template>
