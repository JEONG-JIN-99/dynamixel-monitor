import { test, expect } from "@playwright/test";

test("live CSV, original-time history, reload, mock switch and routes", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const samples: number[] = [];
  page.on("websocket", (socket) =>
    socket.on("framereceived", ({ payload }) => {
      const message = JSON.parse(String(payload));
      if (message.type === "samples") samples.push(message.samples.at(-1).seq);
    }),
  );
  await page.goto("/");
  await expect(page.locator(".source-path")).toContainText("sample.csv");
  await expect(page.locator(".timing-bar")).toContainText("최근 60초");
  await expect(page.locator(".connection-badge")).toContainText("시연 CSV");
  await expect(page.locator(".diagnosis-result")).toContainText("판정 대기");
  await expect(page.locator(".metric-card")).toHaveCount(6);
  await expect(page.locator("canvas")).toHaveCount(3);
  await expect.poll(() => samples.length).toBeGreaterThan(0);
  await page.reload();
  await expect(page.locator(".timing-bar")).toContainText("최근 60초");
  await page.getByRole("button", { name: "가상 데이터 보기" }).click();
  await expect(page.locator(".source-path")).toContainText(
    "가상 데이터 · 실제 모터와 연결되지 않음",
  );
  await page.getByRole("button", { name: "실험 CSV로 돌아가기" }).click();
  await expect(page.locator(".source-path")).toContainText("sample.csv");
  await page.getByRole("link", { name: "상세 분석" }).click();
  await expect(page.locator(".trends-page")).toBeVisible();
  await page.reload();
  await expect(page.locator(".trends-page")).toBeVisible();
  await page.getByRole("link", { name: "개요", exact: true }).click();
  await expect(page.locator(".timing-bar")).toContainText("최근 60초");
  await page
    .getByRole("button", { name: "차트 확대", exact: true })
    .first()
    .click();
  await expect(page.locator(".chart-card.expanded")).toBeVisible();
  await page.getByRole("button", { name: "차트 축소", exact: true }).click();
  expect(errors).toEqual([]);
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
    await expect(page.locator("canvas")).toHaveCount(3);
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
    await expect(page.locator(".motor-visual img")).toBeVisible();
    expect(
      await page
        .locator(".motor-visual img")
        .evaluate(
          (img: HTMLImageElement) => img.complete && img.naturalWidth > 0,
        ),
    ).toBe(true);
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

test("direct Mock entry: repeated CSV clicks, back and reload stay on CSV", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/?source=mock");
  await expect(page.locator(".source-path")).toContainText(
    "가상 데이터 · 실제 모터와 연결되지 않음",
  );
  await page.getByRole("button", { name: "실험 CSV로 돌아가기" }).dblclick();
  await expect(page.locator(".source-path")).toContainText("sample.csv");
  await expect(page).toHaveURL("http://127.0.0.1:8765/");
  await expect(
    page.getByRole("button", { name: "실험 CSV로 돌아가기" }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("link", { name: "상세 분석" }).click();
  await page.goBack();
  await expect(page).toHaveURL("http://127.0.0.1:8765/");
  await expect(page.locator(".source-path")).toContainText("sample.csv");
  await page.reload();
  await expect(page.locator(".source-path")).toContainText("sample.csv");
  await expect(page).not.toHaveURL(/source=mock/);
  expect(errors).toEqual([]);
});

test("Mock selection stays consistent through menu navigation and browser history", async ({
  page,
}) => {
  await page.goto("/?source=mock");
  await page.getByRole("link", { name: "상세 분석" }).click();
  await expect(page).toHaveURL(/trends\?source=mock/);
  await page.reload();
  await expect(
    page.getByRole("button", { name: "가상 데이터 보기" }),
  ).toHaveAttribute("aria-pressed", "true");
  await page.getByRole("link", { name: "개요", exact: true }).click();
  await expect(page.locator(".source-path")).toContainText(
    "가상 데이터 · 실제 모터와 연결되지 않음",
  );
  await page.getByRole("button", { name: "실험 CSV로 돌아가기" }).click();
  await expect(page.locator(".source-path")).toContainText("sample.csv");
  await page.goBack();
  await expect(page).toHaveURL(/trends\?source=mock/);
  await expect(
    page.getByRole("button", { name: "가상 데이터 보기" }),
  ).toHaveAttribute("aria-pressed", "true");
});

test("CSV selection clears Mock values even when the server cannot be reached", async ({
  page,
  context,
}) => {
  await page.goto("/?source=mock");
  await expect(page.locator(".source-path")).toContainText(
    "가상 데이터 · 실제 모터와 연결되지 않음",
  );
  await context.setOffline(true);
  try {
    await page.getByRole("button", { name: "실험 CSV로 돌아가기" }).click();
    await expect(page.locator(".source-path")).toContainText("CSV 연결 대기");
    await expect(page.locator(".timing-bar")).toContainText(
      "데이터 수집 주기 —",
    );
    await expect(page.locator(".metric-value").first()).toContainText("—");
    await expect(page).not.toHaveURL(/source=mock/);
    await expect(page.locator(".notice").first()).toBeVisible();
  } finally {
    await context.setOffline(false);
  }
});

test("velocity legend hides plotted lines and preserves selection across updates", async ({
  page,
}) => {
  let batches = 0;
  page.on("websocket", (socket) =>
    socket.on("framereceived", ({ payload }) => {
      if (JSON.parse(String(payload)).type === "samples") batches++;
    }),
  );
  await page.goto("/");
  await expect(page.locator(".source-path")).toContainText("sample.csv");
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
  await page.goto("/");
  await expect(page.locator(".metric-value").first()).toContainText("111");
  await expect(page.locator(".diagnosis-result")).toContainText("판정 대기");
  await page
    .getByRole("combobox", { name: "모터종류" })
    .selectOption("XM430-W350:2");
  await expect(page.locator(".metric-value").first()).toContainText("222");
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
  await expect(page.locator(".metric-value").first()).toContainText("225");
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
  await expect(page.locator(".connection-badge")).toContainText("서버 수신");
  await expect.poll(() => frames).toBeGreaterThan(2);
  const before = await page.locator(".metric-value").first().textContent();
  await expect(page.locator(".metric-value").first()).not.toHaveText(before!);
  disconnect!();
  await expect(page.locator(".connection-badge")).toContainText("연결 대기");
  // Let the final queued screen update settle, then prove no local generator runs.
  await page.waitForTimeout(150);
  const stopped = await page.locator(".metric-grid").textContent();
  await page.waitForTimeout(600);
  await expect(page.locator(".metric-grid")).toHaveText(stopped!);
  await expect(page.locator(".notice")).toContainText(
    "가상 데이터 서버 연결 대기",
  );
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
    f(sample.registers[132].raw),
  );
  await expect(page.locator(".metric-value").nth(2)).toContainText(
    f(sample.registers[126].raw * 0.00269, 3),
  );
  await page.getByRole("link", { name: "모터", exact: true }).click();
  await expect(page.locator(".provided-count")).toHaveText("값 제공 53 / 53개");
  await expect(page.locator("tr[data-address='126'] .register-raw")).toHaveText(
    f(sample.registers[126].raw),
  );
  await page.getByRole("link", { name: "상세 분석", exact: true }).click();
  const error = page
    .locator(".chart-card")
    .filter({
      has: page.getByRole("heading", { name: "위치 추종 오차", exact: true }),
    });
  await expect(error.locator(".chart-current strong")).toHaveText(
    f(sample.registers[132].raw - sample.registers[140].raw),
  );
});
