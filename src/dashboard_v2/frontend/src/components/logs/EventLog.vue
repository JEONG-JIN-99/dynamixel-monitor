<script setup lang="ts">
import { computed } from "vue";
import { useMotorStore } from "../../stores/motorStore";
const store = useMotorStore();
const rows = computed(() => [...store.events].reverse().slice(0, 50));
</script>
<template>
  <section class="panel event-card">
    <div class="panel-title">
      <h2>
        Event log <span class="count">{{ store.events.length }}</span>
      </h2>
      <span class="tiny">최근 50개 표시 · 최대 200개 보관</span>
    </div>
    <div class="event-table">
      <table>
        <thead>
          <tr>
            <th>TIME</th>
            <th>LEVEL</th>
            <th>MESSAGE</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="event in rows" :key="event.id">
            <td>
              {{
                new Date(event.time).toLocaleTimeString("ko-KR", {
                  hour12: false,
                })
              }}
            </td>
            <td>
              <span class="event-level" :class="event.severity">{{
                event.severity.toUpperCase()
              }}</span>
            </td>
            <td>{{ event.message }}</td>
          </tr>
          <tr v-if="!rows.length">
            <td colspan="3" class="empty-events">
              아직 기록된 이벤트가 없습니다.
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
