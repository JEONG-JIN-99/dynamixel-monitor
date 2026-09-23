import type {
  ConnectionState,
  Message,
  SourceMode,
  Sample,
  RegisterSample,
} from "../types/motor";
import { normalizeMessage } from "./telemetryAdapter";

export function connectMotorData(
  mode: SourceMode,
  onMessage: (message: Message) => void,
  onConnection: (state: ConnectionState) => void,
) {
  let stopped = false;
  let socket: WebSocket | null = null;
  let retry: ReturnType<typeof setTimeout> | undefined;
  let delay = 500;
  function connect() {
    if (stopped) return;
    onConnection("connecting");
    socket = new WebSocket(
      `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/telemetry${mode === "mock" ? "?source=mock" : ""}`,
    );
    socket.onopen = () => {
      delay = 500;
      onConnection("connected");
    };
    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as Message<
          Sample | RegisterSample
        >;
        if (message.schemaVersion !== 1) throw new Error("Unsupported schema");
        onMessage(normalizeMessage(message));
      } catch {
        socket?.close(1002, "Invalid telemetry message");
      }
    };
    socket.onerror = () => socket?.close();
    socket.onclose = () => {
      if (stopped) return;
      onConnection("disconnected");
      retry = setTimeout(connect, delay);
      delay = Math.min(10000, delay * 2);
    };
  }
  connect();
  return () => {
    stopped = true;
    clearTimeout(retry);
    if (socket) {
      socket.onclose = null;
      socket.onmessage = null;
      socket.close();
    }
  };
}
