import { test, expect } from "@playwright/test";
test("register-only backend payload draws charts and independent diagnosis", async ({
  page,
}) => {
  let send: ((message: string) => void) | undefined;
  let base: any;
  await page.routeWebSocket("**/ws/telemetry", (client) => {
    const server = client.connectToServer();
    server.onMessage((raw) => {
      const m = JSON.parse(String(raw));
      if (m.type !== "snapshot" || base) return;
      base = m;
      const old = m.history.at(-1);
      m.history = Array.from({ length: 21 }, (_, i) => ({
        serverSessionId: m.serverSessionId,
        sourceSessionId: m.sourceSessionId,
        runId: m.runId,
        id: 1,
        model: "XM430-W210",
        seq: 10000 + i,
        elapsedMs: i * 100,
        timestamp: 1000 + i * 100,
        receivedAt: 1000 + i * 100,
        registers: Object.fromEntries(
          Object.entries({
            11: 4,
            64: 1,
            70: 0,
            123: 2,
            122: 1,
            126: 100,
            128: 10,
            136: 5,
            132: 100 + i,
            140: 90 + i,
            116: 4000,
            124: 50,
            144: 120,
            146: 32,
          }).map(([a, v]) => [
            a,
            { raw: v, status: "received", receivedAt: 1000 + i * 100 },
          ]),
        ),
        diagnosis:
          i < 10
            ? { state: "normal", codes: [] }
            : { state: "fault", codes: ["friction"] },
      }));
      base.history = m.history;
      send = (text) => client.send(text);
      client.send(JSON.stringify(m));
    });
  });
  await page.goto("/trends");
  await expect(page.locator(".chart-card")).toHaveCount(8);
  const current = page
    .locator(".chart-card")
    .filter({ has: page.getByRole("heading", { name: "전류", exact: true }) });
  const error = page.locator(".chart-card").filter({
    has: page.getByRole("heading", { name: "위치 추종 오차", exact: true }),
  });
  await expect(current.locator(".chart-current")).toContainText("0.269");
  await expect(error.locator(".chart-current")).toContainText("10");
  await expect(page.locator(".analysis-verdict")).toContainText("마찰");
  const last = base.history.at(-1);
  send!(
    JSON.stringify({
      schemaVersion: 1,
      type: "samples",
      serverSessionId: base.serverSessionId,
      sourceSessionId: base.sourceSessionId,
      samples: [
        {
          ...last,
          seq: 11000,
          elapsedMs: 2100,
          diagnosis: null,
          registers: {
            ...last.registers,
            126: { raw: null, status: "error", receivedAt: 3100 },
          },
        },
      ],
    }),
  );
  await expect(current.locator(".chart-current strong")).toHaveText("—");
  await expect(page.locator(".analysis-verdict")).toContainText("판정 대기");
});
test("pause, resume and source change never retain frozen mock readings", async ({
  page,
}) => {
  let frames = 0;
  page.on("websocket", (socket) =>
    socket.on("framereceived", ({ payload }) => {
      if (JSON.parse(String(payload)).type === "samples") frames++;
    }),
  );
  await page.goto("/trends?source=mock");
  await expect(page.locator(".connection-badge")).toContainText("서버 수신");
  await expect.poll(() => frames).toBeGreaterThan(0);
  const beforeFrames = frames;
  await page
    .getByRole("button", { name: "화면 일시정지", exact: true })
    .click();
  const value = page.locator(".chart-current").first();
  const before = await value.textContent();
  await expect.poll(() => frames).toBeGreaterThan(beforeFrames + 2);
  await expect(value).toHaveText(before!);
  await page.getByRole("button", { name: "화면 재개", exact: true }).click();
  await expect(value).not.toHaveText(before!);
  await page
    .getByRole("button", { name: "화면 일시정지", exact: true })
    .click();
  await page.getByRole("button", { name: "실험 CSV로 돌아가기" }).click();
  await expect(
    page.getByRole("button", { name: "화면 일시정지", exact: true }),
  ).toHaveAttribute("aria-pressed", "false");
  await expect(page.locator(".analysis-verdict")).toContainText("판정 대기");
});
for (const width of [1920, 1440, 390]) {
  test(`analysis layout ${width}`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.setViewportSize({ width, height: 1080 });
    await page.goto("/trends?source=mock");
    await expect(page.locator("canvas")).toHaveCount(8);
    await expect(page.locator(".chart-current strong").first()).not.toHaveText(
      "—",
    );
    await page
      .getByRole("button", { name: "화면 일시정지", exact: true })
      .click();
    await page.getByRole("checkbox", { name: /설정 한계선 표시/ }).check();
    await page.getByRole("checkbox", { name: /설정 한계선 표시/ }).uncheck();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: `../runtime/trends-${width}.png`,
      fullPage: true,
    });
    await page
      .getByRole("button", { name: "차트 확대", exact: true })
      .first()
      .click();
    await expect(page.locator(".chart-card.expanded")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.locator(".chart-card.expanded")).toHaveCount(0);
    expect(errors).toEqual([]);
  });
}

test("linked cursor and legends work on analysis charts", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1080 });
  await page.goto("/trends?source=mock");
  await page
    .getByRole("button", { name: "화면 일시정지", exact: true })
    .click();
  const charts = page.locator(".chart-card");
  await charts
    .first()
    .locator(".chart")
    .hover({ position: { x: 180, y: 80 } });
  await expect(charts.nth(1).locator(".telemetry-tooltip")).toBeVisible();
  await expect(charts.nth(1).locator(".telemetry-tooltip")).toContainText(
    "측정 속도",
  );
  const trajectory = charts
    .nth(1)
    .getByRole("button", { name: "목표 궤적", exact: true });
  await trajectory.click();
  await expect(trajectory).toHaveAttribute("aria-pressed", "false");
  await expect(
    charts.nth(1).getByRole("button", { name: "측정 속도", exact: true }),
  ).toBeDisabled();
});

test("limit switch changes all four plots and restores their measured-value scale", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1080 });
  await page.goto("/trends?source=mock");
  await expect(page.locator(".chart-current strong").first()).not.toHaveText(
    "—",
  );
  await page
    .getByRole("button", { name: "화면 일시정지", exact: true })
    .click();
  const titles = ["전류", "PWM", "입력 전압", "내부 온도"];
  const plots = titles.map((title) =>
    page
      .locator(".chart-card")
      .filter({ has: page.getByRole("heading", { name: title, exact: true }) })
      .locator("canvas"),
  );
  const capture = async () => {
    await page.mouse.move(0, 0);
    await page.evaluate(
      () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ),
    );
    const images = [];
    for (const plot of plots) images.push(await plot.screenshot());
    return images;
  };
  const before = await capture();
  const toggle = page.getByRole("checkbox", {
    name: "설정 한계선 표시",
    exact: true,
  });
  await toggle.check();
  const enabled = await capture();
  for (let i = 0; i < plots.length; i++)
    expect(enabled[i]!.equals(before[i]!), titles[i]).toBe(false);
  await page
    .locator(".chart-card")
    .filter({
      has: page.getByRole("heading", { name: "내부 온도", exact: true }),
    })
    .screenshot({ path: "../runtime/temperature-limits-enabled.png" });
  await toggle.uncheck();
  const restored = await capture();
  for (let i = 0; i < plots.length; i++)
    expect(restored[i]!.equals(before[i]!), titles[i]).toBe(true);
});
