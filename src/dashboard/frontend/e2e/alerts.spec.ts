import { selectSource } from "./sourceNavigation";
import { test, expect, type Page } from "@playwright/test";

const storageKey = "motor-dashboard.diagnosis-alerts.v1";
async function stream(page: Page) {
  let seq = 0;
  let ready = false;
  let send: (data: string) => void = () => {
    throw new Error("Socket not ready");
  };
  let close: () => void = () => {};
  const history: any[] = [];
  const identity = {
    serverSessionId: "alerts-test-server",
    sourceSessionId: "alerts-test-source",
    runId: "alerts-test-run",
  };
  const system = {
    sourceMode: "csv",
    validity: "valid",
    experimentStatus: "running",
    dataAgeSec: 0,
    configuredHz: 10,
    observedHz: 10,
    expectedFlushSec: 0.1,
    error: null,
    readerCaughtUp: true,
    writerActive: true,
  };
  function row(codes: string[] | null, patch = {}) {
    const n = ++seq;
    return {
      ...identity,
      busId: "USB-1",
      seq: n,
      id: 1,
      model: "XM430-W210",
      elapsedMs: n * 100,
      timestamp: 1790000000000 + n * 100,
      receivedAt: 1790000000000 + n * 100,
      pcTime: "",
      current: 0.269,
      velocity: 0,
      position: 1000,
      voltage: 12,
      temperature: 33,
      pwm: 10,
      velocityTrajectory: 0,
      positionTrajectory: 1000,
      goalPosition: 1000,
      loadPercent: null,
      moving: false,
      hwError: 0,
      movingStatus: 1,
      realtimeTick: n * 100,
      diagnosis:
        codes === null
          ? null
          : { state: codes.length ? "fault" : "normal", codes },
      ...patch,
    };
  }
  history.push(row([]));
  await page.routeWebSocket("**/ws/telemetry*", (socket) => {
    system.sourceMode =
      new URL(socket.url()).searchParams.get("source") === "mock"
        ? "mock"
        : "csv";
    ready = true;
    send = (data) => socket.send(data);
    close = () => socket.close();
    socket.send(
      JSON.stringify({
        schemaVersion: 1,
        type: "snapshot",
        ...identity,
        history,
        latest: history.at(-1),
        seq,
        retentionSec: 60,
        capacity: 12000,
        events: [],
        metadata: [],
        system,
        experiment: {
          runId: identity.runId,
          status: system.experimentStatus,
          sampleIntervalSec: 0.1,
          startedAt: "2026-09-21T12:00:00Z",
        },
      }),
    );
  });
  return {
    ready: () => ready,
    seed(codes: string[]) {
      history.push(row(codes));
    },
    complete() {
      system.experimentStatus = "completed";
      system.writerActive = false;
    },
    push(codes: string[] | null, patch = {}) {
      const sample = row(codes, patch);
      history.push(sample);
      send(
        JSON.stringify({
          schemaVersion: 1,
          type: "samples",
          ...identity,
          samples: [sample],
        }),
      );
    },
    disconnect: () => close(),
    stale() {
      send(
        JSON.stringify({
          schemaVersion: 1,
          type: "system",
          ...identity,
          system: { ...system, validity: "stale" },
          experiment: { runId: identity.runId },
          metadata: [],
        }),
      );
    },
  };
}

test("individual confirmation survives reload without clearing other alerts or resolving faults", async ({
  page,
}) => {
  const source = await stream(page);
  await page.goto("/?source=csv");
  await expect(page.locator(".connection-badge")).toContainText("수신 중");
  source.push(["overload"]);
  source.push(["overload"]);
  source.push(["overload", "friction"]);
  await expect(page.locator(".alert-badge")).toHaveText("2");
  await page.getByRole("link", { name: "알림", exact: true }).click();
  await expect(page.locator(".alert-row")).toHaveCount(2);
  await expect(page.locator(".alert-badge")).toHaveText("2");
  const overload = page.locator(".alert-row").filter({ hasText: "과부하" });
  await overload.locator(".alert-read-target").click();
  await expect(overload).toHaveAttribute("data-read", "true");
  await expect(overload).toHaveAttribute("data-status", "read");
  await expect(page.locator(".alert-badge")).toHaveText("1");
  await overload.locator(".alert-read-target").click();
  await expect(page.locator(".alert-badge")).toHaveText("1");
  await page.reload();
  await expect(page.locator(".alert-row")).toHaveCount(2);
  await expect(page.locator(".alert-badge")).toHaveText("1");
  await expect(overload).toHaveAttribute("data-read", "true");
  source.push(null);
  await expect(page.locator('.alert-row[data-active="false"]')).toHaveCount(2);
  source.push([]);
  await expect(page.locator('.alert-row[data-active="false"]')).toHaveCount(2);
  await expect(page.locator(".alert-badge")).toHaveText("1");
  const friction = page.locator(".alert-row").filter({ hasText: "마찰" });
  await friction.locator(".alert-read-target").focus();
  await page.keyboard.press("Space");
  await expect(page.locator(".alert-badge")).toHaveCount(0);
  source.push(["overload"]);
  await expect(page.locator(".alert-badge")).toHaveText("1");
  await expect(page.locator('.alert-row[data-read="false"]')).toHaveCount(1);
  await page.reload();
  await expect(page.locator(".alert-row")).toHaveCount(3);
  await expect(page.locator(".alert-badge")).toHaveText("1");
});

test("visible arrivals, tab return and source switches never auto-confirm alerts", async ({
  page,
}) => {
  const source = await stream(page);
  await page.goto("/alerts?source=csv");
  await expect(page.locator(".alerts-empty")).toBeVisible();
  source.push(["overload"]);
  await expect(page.locator(".alert-badge")).toHaveText("1");
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "hidden",
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  source.push(["overload", "friction"]);
  await expect(page.locator(".alert-badge")).toHaveText("2");
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "visible",
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect(page.locator(".alert-badge")).toHaveText("2");
  source.stale();
  await expect(page.locator('.alert-row[data-active="false"]')).toHaveCount(2);
  await selectSource(page, "mock");
  await expect(page.locator(".alert-row")).toHaveCount(2);
  await selectSource(page, "csv");
  await expect(page.locator(".alert-row")).toHaveCount(2);
  await expect(page.locator(".alert-badge")).toHaveText("2");
  source.disconnect();
  await expect(page.locator('.alert-row[data-active="false"]')).toHaveCount(2);
});

test("pagination, search and filtering preserve unread counts until a row is activated", async ({
  page,
}) => {
  const source = await stream(page);
  await page.goto("/alerts?source=csv");
  await expect(page.locator(".alerts-empty")).toBeVisible();
  for (let id = 1; id <= 27; id++) source.push(["overload"], { id });
  await expect(page.locator(".alert-badge")).toHaveText("27");
  await expect(page.locator(".alert-row")).toHaveCount(25);
  await page.getByRole("button", { name: "다음 알림 페이지" }).click();
  await expect(page.locator(".alert-row")).toHaveCount(2);
  await expect(page.locator(".alert-badge")).toHaveText("27");
  await page.locator(".alert-read-target").first().focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(".alert-badge")).toHaveText("26");
  await page.getByRole("searchbox", { name: "알림 검색" }).fill("ID 27");
  await expect(page.locator(".alert-row")).toHaveCount(1);
  await page.getByRole("button", { name: "발생 중", exact: true }).click();
  await expect(page.locator(".alert-badge")).toHaveText("26");
  await page.locator(".alert-read-target").click();
  await expect(page.locator(".alert-badge")).toHaveText("25");
});

test("storage failures and invalid saved data leave the dashboard usable", async ({
  page,
}) => {
  await page.addInitScript((key) => {
    localStorage.setItem(key, "{bad");
    Storage.prototype.setItem = () => {
      throw new DOMException("Quota exceeded", "QuotaExceededError");
    };
  }, storageKey);
  const source = await stream(page);
  await page.goto("/alerts?source=csv");
  await expect(page.locator(".alerts-notice").first()).toContainText(
    "알림 기록 오류",
  );
  source.push(["overload"]);
  await expect(page.locator(".alert-row")).toHaveCount(1);
  await expect(page.locator(".alerts-notice").first()).toContainText(
    "알림 기록 오류",
  );
});

for (const width of [1440, 900, 390]) {
  test("alerts layout and filters " + width, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    const source = await stream(page);
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/?source=csv");
    await expect(page.locator(".connection-badge")).toContainText("수신 중");
    source.push(["overload", "friction"]);
    source.push(["friction"]);
    source.push(["undervoltage"], {
      id: 2,
      model: "XM430-W350",
      busId: "USB-2",
    });
    source.push(["gear_backlash"], {
      id: 3,
      model: "XM430-W350",
      busId: "USB-2",
    });
    source.push(null, { id: 3, model: "XM430-W350", busId: "USB-2" });
    await expect(page.locator(".alert-badge")).toBeVisible();
    await expect(page.locator(".alert-badge")).toHaveText("4");
    await page.getByRole("link", { name: "알림", exact: true }).click();
    await expect(page.locator(".alert-row")).toHaveCount(4);
    await page.screenshot({
      path: "../runtime/alerts-" + width + ".png",
      fullPage: true,
    });
    await expect(page.locator(".alerts-summary .resolved strong")).toHaveText(
      "1건",
    );
    await page.getByRole("button", { name: "해제됨", exact: true }).click();
    await expect(page.locator(".alert-row")).toHaveCount(1);
    await expect(page.locator(".alert-row")).toContainText("과부하");
    await expect(page.locator(".alert-row")).toHaveAttribute(
      "data-read",
      "false",
    );
    await expect(page.locator(".alert-badge")).toHaveText("4");
    await page.getByRole("button", { name: "전체", exact: true }).click();
    await page.locator(".alert-read-target").first().click();
    await expect(page.locator(".alert-badge")).toHaveText("3");
    await page.getByRole("button", { name: "확인", exact: true }).click();
    await expect(page.locator(".alert-row")).toHaveCount(1);
    await page.getByRole("button", { name: "전체", exact: true }).click();
    await page.getByRole("searchbox", { name: "알림 검색" }).fill("XM430-W350");
    await expect(page.locator(".alert-row")).toHaveCount(2);
    await page.getByRole("searchbox", { name: "알림 검색" }).fill("없는 알림");
    await expect(page.locator(".alerts-empty")).toContainText("조건에 맞는");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    expect(errors).toEqual([]);
  });
}

test("completed mock history does not create four unread alerts after entry, reload or source switch", async ({
  page,
}) => {
  const source = await stream(page);
  source.seed(["friction"]);
  source.seed(["overload"]);
  source.seed([]);
  source.seed(["friction"]);
  source.seed(["overload"]);
  source.seed([]);
  source.complete();
  await page.goto("/alerts?source=mock");
  await expect.poll(source.ready).toBe(true);
  await expect(page.locator(".alerts-empty")).toBeVisible();
  await expect(page.locator(".alert-badge")).toHaveCount(0);
  await page.reload();
  await expect(page.locator(".alerts-empty")).toBeVisible();
  await expect(page.locator(".alert-badge")).toHaveCount(0);
  await selectSource(page, "csv");
  await selectSource(page, "mock");
  await expect(page.locator(".alert-badge")).toHaveCount(0);
  await expect(page.getByText("상태 확인 대기", { exact: true })).toHaveCount(
    0,
  );
  await expect(
    page.getByRole("button", { name: "해제됨", exact: true }),
  ).toBeVisible();
});
test("mock row confirmation changes summary, filters and badge and survives reload", async ({
  page,
}) => {
  const source = await stream(page);
  await page.goto("/alerts?source=mock");
  await expect.poll(source.ready).toBe(true);
  await expect(page.locator(".alerts-empty")).toBeVisible();
  source.push(["friction", "overload"]);
  await expect(page.locator(".alerts-summary .pending strong")).toContainText(
    "2",
  );
  await expect(page.locator(".alert-badge")).toHaveText("2");
  await page.getByRole("button", { name: "미확인", exact: true }).click();
  await page.locator(".alert-read-target").first().click();
  await expect(page.locator(".alert-row")).toHaveCount(1);
  await expect(page.locator(".alerts-summary .success strong")).toContainText(
    "1",
  );
  await expect(page.locator(".alert-badge")).toHaveText("1");
  await page.getByRole("button", { name: "확인", exact: true }).click();
  await expect(page.locator(".alert-row")).toHaveCount(1);
  await expect(
    page.locator(".alert-row .alert-time time").last(),
  ).not.toHaveText("—");
  await page.reload();
  await expect(page.locator(".alert-row")).toHaveCount(2);
  await expect(page.locator(".alert-badge")).toHaveText("1");
  await expect(page.locator('.alert-row[data-read="true"]')).toHaveCount(1);
});
