import { test, expect } from "@playwright/test";
test("shaft follows signed cumulative position, stops on missing data and preserves origin", async ({
  page,
}) => {
  let send: (value: string) => void = () => {};
  let seq = 1,
    runId = "shaft-run";
  const row = (
    position: number | null,
    elapsedMs: number,
    basePosition: number | null = 100,
  ) => ({
    serverSessionId: "shaft-server",
    sourceSessionId: "shaft-source",
    runId,
    busId: "test",
    id: 1,
    model: "XM430-W210",
    seq: seq++,
    elapsedMs,
    timestamp: 1790000000000 + elapsedMs,
    receivedAt: 1790000000000 + elapsedMs,
    position,
    basePosition,
    velocity: 0,
    current: 0.1,
    pwm: 0,
    voltage: 12,
    temperature: 30,
    moving: false,
    positionTrajectory: position,
    velocityTrajectory: 0,
    goalPosition: position,
    diagnosis: { state: "normal", codes: [] },
  });
  const snapshot = (sample: any) => ({
    schemaVersion: 1,
    type: "snapshot",
    serverSessionId: "shaft-server",
    sourceSessionId: "shaft-source",
    runId,
    history: [sample],
    latest: sample,
    retentionSec: 60,
    capacity: 12000,
    seq: sample.seq,
    metadata: [],
    events: [],
    experiment: { runId, sampleIntervalSec: 0.1, status: "running" },
    system: {
      validity: "valid",
      experimentStatus: "running",
      readerCaughtUp: true,
      writerActive: true,
      configuredHz: 10,
    },
  });
  await page.routeWebSocket("**/ws/telemetry", (socket) => {
    send = (s) => socket.send(s);
    send(JSON.stringify(snapshot(row(100, 0))));
  });
  await page.goto("/?source=csv");
  const model = page.locator(".motor-model");
  await expect(model).toHaveAttribute("data-ready", "true");
  await expect(model.locator("canvas")).toBeVisible();
  async function push(
    position: number | null,
    elapsedMs: number,
    base: number | null = 100,
  ) {
    send(
      JSON.stringify({
        schemaVersion: 1,
        type: "samples",
        serverSessionId: "shaft-server",
        sourceSessionId: "shaft-source",
        samples: [row(position, elapsedMs, base)],
      }),
    );
  }
  async function angle(value: number) {
    await expect
      .poll(async () => Number(await model.getAttribute("data-angle")))
      .toBeCloseTo(value, 3);
  }
  await push(1124, 100);
  await angle(Math.PI / 2);
  await push(100 + 4096 * 3, 200);
  await angle(Math.PI * 6);
  await push(100 - 1024, 300);
  await angle(-Math.PI / 2);
  await push(null, 400);
  await angle(-Math.PI / 2);
  await page.waitForTimeout(200);
  await angle(-Math.PI / 2);
  await push(100, 500);
  await angle(0);
  await push(1124, 70000);
  await angle(Math.PI / 2);
  await expect(model).toHaveAttribute("data-origin", "100");
  await page.getByRole("link", { name: "알림", exact: true }).click();
  await page.getByRole("link", { name: "개요", exact: true }).click();
  await angle(Math.PI / 2);
  runId = "shaft-run-2";
  send(JSON.stringify(snapshot(row(700, 0, 700))));
  await angle(0);
  await expect(model).toHaveAttribute("data-origin", "700");
  // No supplied base: retain the first valid position rather than the sliding buffer's first row.
  runId = "shaft-run-3";
  send(JSON.stringify(snapshot(row(-500, 0, null))));
  await angle(0);
  await push(524, 80000, null);
  await angle(Math.PI / 2);
  await expect(model).toHaveAttribute("data-origin", "-500");
  await page.screenshot({ path: "../runtime/motor-3d.png", fullPage: true });
});
