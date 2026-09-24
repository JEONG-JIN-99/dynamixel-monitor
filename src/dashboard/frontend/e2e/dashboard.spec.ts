import { test, expect } from "@playwright/test";
import { selectSource } from "./sourceNavigation";

test("default demo has no developer copy and survives navigation and reload", async ({
  page,
}) => {
  const errors: string[] = [];
  const sources: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("websocket", (socket) => sources.push(socket.url()));
  await page.goto("/");
  await expect(page.locator(".metric-value").first()).not.toContainText("—");
  await expect(
    page.locator(
      ".source-selector, .source-path, .diagnosis-result p, .run-state small",
    ),
  ).toHaveCount(0);
  await expect(page.locator(".app-header")).not.toContainText("가상 데이터");
  await expect(page.locator(".metric-card")).toHaveCount(3);
  await page.getByRole("link", { name: "상세 분석", exact: true }).click();
  await page.reload();
  await page.getByRole("link", { name: "개요", exact: true }).click();
  await expect(page.locator(".metric-value").first()).not.toContainText("—");
  expect(
    sources.every((url) => url.endsWith("/ws/telemetry?source=mock")),
  ).toBe(true);
  await page
    .getByRole("button", { name: "차트 확대", exact: true })
    .first()
    .click();
  await expect(page.locator(".chart-card.expanded")).toBeVisible();
  await page.getByRole("button", { name: "차트 축소", exact: true }).click();
  expect(errors).toEqual([]);
});

test("explicit CSV remains connected across navigation and reload", async ({
  page,
}) => {
  await page.goto("/?source=csv");
  await expect(page.locator(".diagnosis-result")).toContainText("판정 대기");
  await expect(page.locator(".connection-badge")).toContainText("수신 중");
  await page.getByRole("link", { name: "상세 분석", exact: true }).click();
  await expect(page).toHaveURL(/trends\?source=csv/);
  await page.reload();
  await page.getByRole("link", { name: "개요", exact: true }).click();
  await expect(page).toHaveURL(/source=csv/);
  await expect(page.locator(".diagnosis-result")).toContainText("판정 대기");
});

test("changing source while offline clears mock readings", async ({
  page,
  context,
}) => {
  await page.goto("/");
  await expect(page.locator(".metric-value").first()).not.toContainText("—");
  await context.setOffline(true);
  try {
    await selectSource(page, "csv");
    await expect(page.locator(".metric-value").first()).toContainText("—");
    await expect(page.locator(".notice")).toHaveText("연결 대기");
  } finally {
    await context.setOffline(false);
  }
});

for (const size of [
  { width: 1920, height: 1080 },
  { width: 1600, height: 900 },
  { width: 1440, height: 900 },
  { width: 390, height: 844 },
]) {
  test(`layout ${size.width} × ${size.height}`, async ({ page }) => {
    await page.setViewportSize(size);
    await page.goto("/?source=mock");
    await expect(page.locator(".timing-bar")).toContainText("최근 60초");
    await expect(page.locator(".chart canvas")).toHaveCount(3);
    await expect(page.locator(".metric-value").first()).not.toContainText("—");
    // Wait for chart drawing via an animation frame, not an arbitrary long delay.
    await page.evaluate(
      () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ),
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await expect(page.locator(".timing-bar > div").first()).toContainText(
      "데이터 수집 주기",
    );
    await expect(page.locator(".motor-model")).toHaveAttribute(
      "data-ready",
      "true",
    );
    await expect(page.locator(".motor-model canvas")).toBeVisible();
    if (size.width > 1000) {
      const grid = await page.locator(".overview-grid").boundingBox();
      const diagnosis = await page.locator(".diagnosis-card").boundingBox();
      const position = await page.locator(".chart-card").last().boundingBox();
      expect(diagnosis!.y + diagnosis!.height).toBeLessThanOrEqual(
        grid!.y + grid!.height + 1,
      );
      expect(position!.y + position!.height).toBeLessThanOrEqual(
        grid!.y + grid!.height + 1,
      );
    }
    await page.screenshot({
      path: `../runtime/dashboard-${size.width}.png`,
      fullPage: true,
    });
  });
}

test("velocity legend hides plotted lines and preserves selection across updates", async ({
  page,
}) => {
  let batches = 0;
  page.on("websocket", (socket) =>
    socket.on("framereceived", ({ payload }) => {
      if (JSON.parse(String(payload)).type === "samples") batches++;
    }),
  );
  await page.goto("/?source=csv");
  await expect(page.locator(".connection-badge")).toContainText("수신 중");
  const panel = page.locator(".chart-card").filter({
    has: page.getByRole("heading", { name: "속도", exact: true }),
  });
  const present = panel.getByRole("button", {
    name: "측정값",
    exact: true,
  });
  const trajectory = panel.getByRole("button", {
    name: "궤적",
    exact: true,
  });
  const canvas = panel.locator(".chart");
  const tooltip = panel.locator(".telemetry-tooltip");
  async function showTooltip() {
    await page.mouse.move(0, 0);
    await canvas.hover({ position: { x: 160, y: 60 } });
    await expect(tooltip).toBeVisible();
  }
  await showTooltip();
  await expect(tooltip).toContainText("측정값");
  await expect(tooltip).toContainText("궤적");
  await panel.screenshot({ path: "../runtime/velocity-both.png" });
  await trajectory.click();
  await expect(trajectory).toHaveAttribute("aria-pressed", "false");
  await expect(present).toBeDisabled();
  const before = batches;
  await expect.poll(() => batches).toBeGreaterThan(before);
  await showTooltip();
  await expect(tooltip).toContainText("측정값");
  await expect(tooltip).not.toContainText("궤적");
  await panel.screenshot({ path: "../runtime/velocity-present-only.png" });
  await trajectory.click();
  await present.click();
  await expect(trajectory).toBeDisabled();
  await showTooltip();
  await expect(tooltip).toContainText("궤적");
  await expect(tooltip).not.toContainText("측정값");
  await present.click();
  await expect(present).toHaveAttribute("aria-pressed", "true");
  await expect(trajectory).toHaveAttribute("aria-pressed", "true");
});

test("selected motor drives readings, charts and independent algorithm diagnosis", async ({
  page,
}) => {
  let send: ((message: string) => void) | undefined;
  let base: any;
  await page.routeWebSocket("**/ws/telemetry", (client) => {
    const server = client.connectToServer();
    server.onMessage((raw) => {
      const message = JSON.parse(String(raw));
      if (message.type !== "snapshot" || base) return;
      base = message;
      const row = message.history.at(-1);
      message.metadata = [
        { ...message.metadata[0], id: 1, model: "XM430-W210" },
        { ...message.metadata[0], id: 2, model: "XM430-W350" },
      ];
      message.history = [
        {
          ...row,
          seq: 10001,
          id: 1,
          model: "XM430-W210",
          position: 111,
          current: 0.111,
          diagnosis: null,
          status: "normal",
          condition: "normal",
        },
        {
          ...row,
          seq: 10002,
          id: 2,
          model: "XM430-W350",
          position: 222,
          current: 0.222,
          diagnosis: { state: "fault", codes: ["overload", "friction"] },
        },
      ];
      send = (text) => client.send(text);
      client.send(JSON.stringify(message));
    });
  });
  await page.goto("/?source=csv");
  await expect(page.locator(".chart-current").last()).toContainText("111");
  await expect(page.locator(".diagnosis-result")).toContainText("판정 대기");
  await page
    .getByRole("combobox", { name: "모터종류" })
    .selectOption("XM430-W350:2");
  await expect(page.locator(".chart-current").last()).toContainText("222");
  await expect(page.locator(".chart-current").first()).toContainText("0.222");
  await expect(page.locator(".diagnosis-result")).toContainText(
    "과부하 · 마찰",
  );
  await expect(page.locator(".diagnosis-chip.detected")).toHaveCount(2);
  // Real 100 ms input changes are presented without inventing samples or averaging.
  const last = base.history.at(-1);
  send!(
    JSON.stringify({
      schemaVersion: 1,
      type: "samples",
      serverSessionId: base.serverSessionId,
      sourceSessionId: base.sourceSessionId,
      samples: [1, 2, 3].map((i) => ({
        ...last,
        seq: 10002 + i,
        elapsedMs: last.elapsedMs + i * 100,
        position: 222 + i,
        diagnosis: { state: "normal", codes: [] },
      })),
    }),
  );
  await expect(page.locator(".chart-current").last()).toContainText("225");
  await expect(page.locator(".diagnosis-result")).toContainText("정상");
  await expect(page.locator(".diagnosis-chip.detected")).toHaveCount(0);
});

test("mock updates come from backend frames and stop when its socket closes", async ({
  page,
}) => {
  let disconnect: (() => void) | undefined;
  let block = false;
  let frames = 0;
  await page.routeWebSocket("**/ws/telemetry?source=mock", (client) => {
    if (block) {
      client.close();
      return;
    }
    const server = client.connectToServer();
    server.onMessage((raw) => {
      if (JSON.parse(String(raw)).type === "samples") frames++;
      client.send(raw);
    });
    disconnect = () => {
      block = true;
      client.close();
      server.close();
    };
  });
  await page.goto("/?source=mock");
  await expect(page.locator(".connection-badge")).toContainText("연결됨");
  await expect.poll(() => frames).toBeGreaterThan(2);
  const before = await page.locator(".chart-current").last().textContent();
  await expect(page.locator(".chart-current").last()).not.toHaveText(before!);
  disconnect!();
  await expect(page.locator(".connection-badge")).toContainText("연결 대기");
  // Let the final queued screen update settle, then prove no local generator runs.
  await page.waitForTimeout(150);
  const stopped = await page.locator(".chart-current").last().textContent();
  await page.waitForTimeout(600);
  await expect(page.locator(".chart-current").last()).toHaveText(stopped!);
  await expect(page.locator(".notice")).toContainText("연결 대기");
});

test("backend raw-only contract renders overview, 53-register table and derived analysis", async ({
  page,
}) => {
  let snapshot: any;
  await page.routeWebSocket("**/ws/telemetry?source=mock", (client) => {
    const server = client.connectToServer();
    server.onMessage((raw) => {
      const message = JSON.parse(String(raw));
      if (message.type === "snapshot") {
        snapshot = message;
        client.send(raw);
      }
      // Inspect one actual server snapshot consistently across all pages.
    });
  });
  await page.goto("/?source=mock");
  await expect(page.locator(".metric-value").first()).not.toContainText("—");
  const sample = snapshot.history.at(-1);
  expect(Object.keys(sample.registers)).toHaveLength(53);
  expect(sample.position).toBeUndefined();
  expect(sample.current).toBeUndefined();
  expect(sample.positionError).toBeUndefined();
  const f = (n: number, digits = 0) =>
    n.toLocaleString("ko-KR", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
  await expect(page.locator(".metric-value").first()).toContainText(
    f(sample.registers[146].raw),
  );
  await expect(page.locator(".metric-value").nth(1)).toContainText(
    f(sample.registers[144].raw * 0.1, 1),
  );
  await page.getByRole("link", { name: "모터", exact: true }).click();
  await expect(page.locator(".provided-count")).toHaveText("값 제공 53 / 53개");
  await expect(page.locator("tr[data-address='126'] .register-raw")).toHaveText(
    f(sample.registers[126].raw),
  );
  await page.getByRole("link", { name: "상세 분석", exact: true }).click();
  const error = page.locator(".chart-card").filter({
    has: page.getByRole("heading", { name: "위치 추종 오차", exact: true }),
  });
  await expect(error.locator(".chart-current strong")).toHaveText(
    f(sample.registers[132].raw - sample.registers[140].raw),
  );
});
