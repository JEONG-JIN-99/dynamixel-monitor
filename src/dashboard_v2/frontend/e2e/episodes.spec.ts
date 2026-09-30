import { test, expect } from "@playwright/test";
const base = Date.parse("2026-09-24T14:59:55Z"),
  offset = 4355000;
const codes: (string[] | null)[] = [
  ["friction"],
  [],
  ["overload"],
  ["overload", "friction"],
  ["friction"],
  [],
  ["friction"],
  ["friction"],
  null,
  ["overload"],
];
const frames = codes.map((c, i) => ({
  serverSessionId: "archived-server",
  sourceSessionId: "record:1",
  runId: "record",
  busId: "mock",
  seq: i + 1,
  id: 1,
  model: "XM430-W210",
  elapsedMs: offset + i * 1000,
  timestamp: base + i * 1000,
  receivedAt: base + i * 1000,
  registers: Object.fromEntries(
    Object.entries({
      11: 4,
      126: 100 + i,
      128: i,
      136: i + 1,
      132: 100 + i,
      140: 90 + i,
      116: 200,
      124: 20,
      144: 120,
      146: 32,
    }).map(([a, raw]) => [
      a,
      { raw, receivedAt: base + i * 1000, status: "received" },
    ]),
  ),
  diagnosis:
    c == null ? null : { state: c.length ? "fault" : "normal", codes: c },
}));
async function recorded(page: any) {
  await page.route("**/api/runs/record", (route: any) =>
    route.fulfill({
      json: {
        runId: "record",
        source: "mock",
        status: "completed",
        startedAt: new Date(base - offset).toISOString(),
        motorModel: "XM430-W210",
        motorId: 1,
        sampleIntervalSec: 1,
        metadata: [],
      },
    }),
  );
  await page.route("**/api/runs/record/history?**", (route: any) =>
    route.fulfill({
      json: {
        schemaVersion: 1,
        runId: "record",
        serverSessionId: "archived-server",
        sourceSessionId: "record:1",
        throughSeq: 10,
        latestElapsedMs: offset + 9000,
        samples: frames,
      },
    }),
  );
}
test("archived faults are newest first, boundaries honest, clocks and linked zoom work", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await recorded(page);
  await page.setViewportSize({ width: 1440, height: 1050 });
  await page.goto("/logs/record?source=mock");
  await expect(page.locator(".analysis-summary")).toHaveCount(0);
  const rows = page.locator(".fault-table tbody tr");
  await expect(rows).toHaveCount(5);
  await expect(rows.first()).toContainText("과부하");
  await expect(rows.first()).toContainText("시작 미확인");
  await expect(rows.first()).toContainText("종료 미확인");
  await expect(rows.last()).toContainText("조회 구간 이전부터");
  await expect(rows.nth(1)).toContainText("01:12:41");
  const plots = page.locator(".chart-card canvas");
  const before = await plots.first().screenshot();
  await rows.nth(1).click();
  await page.mouse.move(0, 0);
  await page.waitForTimeout(350);
  const zoomed = await plots.first().screenshot();
  expect(zoomed.equals(before)).toBe(false);
  await page
    .locator(".chart-card")
    .first()
    .locator(".chart")
    .hover({ position: { x: 230, y: 90 } });
  await expect(
    page.locator(".chart-card").first().locator(".telemetry-tooltip"),
  ).toContainText("실험 경과");
  await expect(
    page.locator(".chart-card").first().locator(".telemetry-tooltip"),
  ).toContainText("실제 시각");
  await page.getByRole("button", { name: "실제 시각", exact: true }).click();
  await expect(rows.nth(1)).toContainText("2026-09-25 00:00:01");
  await expect(page.locator(".status-history-axis")).toContainText(
    "2026-09-25",
  );
  await page.mouse.move(0, 0);
  await page.screenshot({
    path: "../runtime/record-fault-episodes.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "실험 경과", exact: true }).click();
  await expect(rows.nth(1)).toContainText("01:12:41");
  expect(errors).toEqual([]);
});
test("live analysis keeps verdict and clicking an episode pauses only the view", async ({
  page,
}) => {
  await page.goto("/trends?source=mock");
  await expect(page.locator(".analysis-summary")).toBeVisible();
  await expect(page.locator(".fault-table tbody tr").first()).toBeVisible();
  await page.locator(".fault-table tbody tr").first().click();
  await expect(
    page.getByRole("button", { name: "화면 재개", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "화면 재개", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "화면 일시정지", exact: true }),
  ).toBeVisible();
});
test("record at mobile width does not overflow and missing wall clock is disabled", async ({
  page,
}) => {
  await recorded(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/logs/record");
  await expect(page.locator(".fault-table tbody tr")).toHaveCount(5);
  await page.getByRole("button", { name: "실제 시각", exact: true }).click();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../runtime/record-fault-episodes-mobile.png",
    fullPage: true,
  });
  await page.route("**/api/runs/record/history?**", (route) =>
    route.fulfill({
      json: {
        schemaVersion: 1,
        runId: "record",
        samples: frames.map((f) => ({ ...f, timestamp: null })),
      },
    }),
  );
  await page.reload();
  await expect(page.locator(".fault-table tbody tr")).toHaveCount(5);
  await expect(
    page.getByRole("button", { name: "실제 시각", exact: true }),
  ).toBeDisabled();
});
