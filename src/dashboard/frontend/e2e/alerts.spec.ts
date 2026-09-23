import { test, expect, type Page } from "@playwright/test";

const storageKey = "motor-dashboard.diagnosis-alerts.v1";
async function stream(page: Page) {
  let seq = 0;
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
  await page.routeWebSocket("**/ws/telemetry", (socket) => {
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
          status: "running",
          sampleIntervalSec: 0.1,
          startedAt: "2026-09-21T12:00:00Z",
        },
      }),
    );
  });
  return {
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

test("unread episodes survive reload, reading clears badge, recovery and recurrence are distinct", async ({
  page,
}) => {
  const source = await stream(page);
  await page.goto("/");
  await expect(page.locator(".connection-badge")).toContainText("수신 중");
  source.push(["overload"]);
  source.push(["overload"]);
  source.push(["overload", "friction"]);
  await expect(page.locator(".alert-badge")).toHaveText("2");
  await expect
    .poll(() =>
      page.evaluate(
        (key) => JSON.parse(localStorage.getItem(key) ?? "{}").records?.length,
        storageKey,
      ),
    )
    .toBe(2);
  await page.reload();
  await expect(page.locator(".alert-badge")).toHaveText("2");
  await page.getByRole("link", { name: "알림", exact: true }).click();
  await expect(page.locator(".alert-row")).toHaveCount(2);
  await expect(page.locator('.alert-row[data-status="active"]')).toHaveCount(2);
  await expect(page.locator(".alert-badge")).toHaveCount(0);
  source.push(null);
  await expect(page.locator('.alert-row[data-status="unknown"]')).toHaveCount(
    2,
  );
  source.push(["friction"]);
  await expect(page.locator('.alert-row[data-status="resolved"]')).toHaveCount(
    1,
  );
  await expect(page.locator('.alert-row[data-status="active"]')).toHaveCount(1);
  source.push([]);
  await expect(page.locator('.alert-row[data-status="resolved"]')).toHaveCount(
    2,
  );
  await page.getByRole("link", { name: "개요", exact: true }).click();
  source.push(["overload"]);
  await expect(page.locator(".alert-badge")).toHaveText("1");
  await page.getByRole("link", { name: "알림", exact: true }).click();
  await expect(page.locator(".alert-row")).toHaveCount(3);
  await page.reload();
  await expect(page.locator(".alert-row")).toHaveCount(3);
  await expect(page.locator(".alert-badge")).toHaveCount(0);
});

test("only a visible alerts page auto-reads arrivals, sources and statuses stay separate", async ({
  page,
}) => {
  const source = await stream(page);
  await page.goto("/alerts");
  await expect(page.locator(".alerts-empty")).toBeVisible();
  source.push(["overload"]);
  await expect(page.locator(".alert-row")).toHaveCount(1);
  await expect(page.locator(".alert-badge")).toHaveCount(0);
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "hidden",
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  source.push(["overload", "friction"]);
  await expect(page.locator(".alert-badge")).toHaveText("1");
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "visible",
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect(page.locator(".alert-badge")).toHaveCount(0);
  source.stale();
  await expect(page.locator('.alert-row[data-status="unknown"]')).toHaveCount(
    2,
  );
  await page.getByRole("button", { name: "가상 데이터 보기" }).click();
  await expect(page.locator(".alerts-empty")).toBeVisible();
  await page.getByRole("button", { name: "실험 CSV로 돌아가기" }).click();
  await expect(page.locator(".alert-row")).toHaveCount(2);
  await expect(page.locator(".alert-badge")).toHaveCount(0);
  source.disconnect();
  await expect(page.locator('.alert-row[data-status="unknown"]')).toHaveCount(
    2,
  );
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
  await page.goto("/alerts");
  await expect(page.locator(".alerts-notice").first()).toContainText(
    "불러오지 못",
  );
  source.push(["overload"]);
  await expect(page.locator(".alert-row")).toHaveCount(1);
  await expect(page.locator(".alerts-notice").first()).toContainText(
    "저장하지 못",
  );
});

for (const width of [1440, 900, 390]) {
  test("alerts layout and filters " + width, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    const source = await stream(page);
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/");
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
    await page.getByRole("button", { name: "해제됨", exact: true }).click();
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
