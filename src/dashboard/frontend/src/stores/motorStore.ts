import { defineStore } from "pinia";
import { computed, ref, shallowRef } from "vue";
import type {
  ConnectionState,
  Experiment,
  LogEvent,
  Message,
  MotorMetadata,
  Sample,
  SourceMode,
  SystemState,
} from "../types/motor";
import { connectMotorData } from "../services/motorDataService";
import { mergeHistory } from "../services/history";
import { useAlertStore } from "./alertStore";

export const useMotorStore = defineStore("motor", () => {
  const alerts = useAlertStore();
  const mode = ref<SourceMode>("csv");
  const connection = ref<ConnectionState>("disconnected");
  const history = shallowRef<Sample[]>([]);
  const experiment = shallowRef<Experiment | null>(null);
  const metadata = shallowRef<MotorMetadata[]>([]);
  const events = shallowRef<LogEvent[]>([]);
  const system = shallowRef<SystemState>(emptySystem());
  const serverSession = ref<string | null>(null);
  const sourceSession = ref<string | null>(null);
  const retentionSec = ref(60);
  let capacity = 12000;
  let close: (() => void) | undefined;
  let generation = 0;
  const latest = computed(() => history.value.at(-1) ?? null);
  const live = computed(
    () =>
      mode.value === "csv" &&
      connection.value === "connected" &&
      system.value.validity === "valid" &&
      system.value.experimentStatus === "running" &&
      system.value.readerCaughtUp &&
      system.value.writerActive === true,
  );

  function emptySystem(): SystemState {
    return {
      sourceMode: "csv",
      validity: "waiting",
      experimentStatus: "unknown",
      dataAgeSec: null,
      configuredHz: null,
      observedHz: null,
      expectedFlushSec: null,
      error: null,
      readerCaughtUp: true,
    };
  }
  function accept(message: Message) {
    if (message.type === "snapshot" || message.type === "reset") {
      serverSession.value = message.serverSessionId;
      sourceSession.value = message.sourceSessionId;
      retentionSec.value = message.retentionSec;
      capacity = message.capacity;
      history.value = mergeHistory(
        [],
        message.history,
        retentionSec.value,
        capacity,
      );
      experiment.value = message.experiment;
      metadata.value = message.metadata;
      events.value = message.events.slice(-200);
      system.value = message.system;
      alerts.beginSession(
        message.serverSessionId,
        message.sourceSessionId,
        message.runId,
      );
      alerts.ingest(
        message.history.filter(
          (sample) =>
            sample.serverSessionId === message.serverSessionId &&
            sample.sourceSessionId === message.sourceSessionId &&
            sample.runId === message.runId,
        ),
      );
      return;
    }
    if (
      message.serverSessionId !== serverSession.value ||
      message.sourceSessionId !== sourceSession.value
    )
      return;
    if (message.type === "samples") {
      const samples = message.samples.filter(
        (sample) =>
          sample.sourceSessionId === sourceSession.value &&
          sample.serverSessionId === serverSession.value &&
          sample.runId === experiment.value?.runId,
      );
      history.value = mergeHistory(
        history.value,
        samples,
        retentionSec.value,
        capacity,
      );
      alerts.ingest(samples);
    } else if (message.type === "system") {
      system.value = message.system;
      experiment.value = message.experiment;
      metadata.value = message.metadata;
      alerts.beginSession(
        message.serverSessionId,
        message.sourceSessionId,
        message.experiment?.runId ?? null,
      );
    } else if (
      message.type === "event" &&
      !events.value.some((event) => event.id === message.event.id)
    ) {
      events.value = [...events.value, message.event].slice(-200);
    }
  }
  function start(source: SourceMode) {
    const activeGeneration = ++generation;
    close?.();
    mode.value = source;
    alerts.start(source);
    history.value = [];
    events.value = [];
    metadata.value = [];
    experiment.value = null;
    serverSession.value = null;
    sourceSession.value = null;
    system.value = { ...emptySystem(), sourceMode: source };
    close = connectMotorData(
      source,
      (message) => {
        if (generation === activeGeneration) accept(message);
      },
      (state) => {
        if (generation === activeGeneration) connection.value = state;
      },
    );
  }
  function stop() {
    ++generation;
    close?.();
    connection.value = "disconnected";
  }
  return {
    mode,
    connection,
    history,
    latest,
    experiment,
    metadata,
    events,
    system,
    live,
    retentionSec,
    start,
    stop,
    accept,
  };
});
