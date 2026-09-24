import { selectSource } from "./sourceNavigation";
import { test, expect } from "@playwright/test";

test("range selector loads CSV history, appends live data and restores after refresh", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/trends?source=mock");
  const select = page.getByRole("combobox", { name: "분석 시간 범위" });
  await expect(select.locator("option")).toHaveText([
    "60초",
    "5분",
    "10분",
    "30분",
    "1시간",
    "전체",
  ]);
  const root = page.locator(".trends-page");
  await expect
    .poll(async () => Number(await root.getAttribute("data-sample-count")))
    .toBeGreaterThan(500);
  expect(
    Number(await root.getAttribute("data-sample-count")),
  ).toBeLessThanOrEqual(601);
  const response = page.waitForResponse(
    (r) =>
      r.url().includes("/api/history?") && r.url().includes("durationSec=0"),
  );
  await select.selectOption("0");
  const history = await (await response).json();
  expect(history.samples[0].elapsedMs).toBe(0);
  await expect
    .poll(async () => Number(await root.getAttribute("data-sample-count")))
    .toBeGreaterThan(1200);
  const elapsed = Number(await root.getAttribute("data-last-elapsed"));
  await expect
    .poll(async () => Number(await root.getAttribute("data-last-elapsed")))
    .toBeGreaterThan(elapsed);
  await expect(page.locator(".status-history")).toBeVisible();
  await expect(
    page.locator(".status-history-segment.normal").first(),
  ).toBeVisible();
  await expect(
    page.locator(".status-history-segment.fault").first(),
  ).toBeVisible();
  await expect(page.locator(".status-history-axis span").first()).toHaveText(
    "0:00",
  );
  const text = await page.locator(".status-history").innerText();
  expect(text).not.toMatch(/알고리즘|가상|MOCK|판정 예시/);
  for (const duration of ["300", "600", "1800", "3600"]) {
    const requested = page.waitForResponse(
      (r) =>
        r.url().includes(`/api/history?`) &&
        r.url().includes(`durationSec=${duration}`),
    );
    await select.selectOption(duration);
    expect((await requested).status()).toBe(200);
    await expect
      .poll(async () => Number(await root.getAttribute("data-sample-count")))
      .toBeGreaterThan(1200);
  }
  await select.selectOption("60");
  await expect
    .poll(async () => Number(await root.getAttribute("data-sample-count")))
    .toBeLessThanOrEqual(601);
  await page.reload();
  await expect(select).toHaveValue("60");
  await select.selectOption("0");
  await expect
    .poll(async () => Number(await root.getAttribute("data-sample-count")))
    .toBeGreaterThan(1200);
  await page.screenshot({
    path: "../runtime/analysis-history-all.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});

test("live frames arriving during history loading are joined and failed requests can retry", async ({
  page,
}) => {
  let frames = 0;
  page.on("websocket", (ws) =>
    ws.on("framereceived", ({ payload }) => {
      if (JSON.parse(String(payload)).type === "samples") frames++;
    }),
  );
  let fetchedEnd = 0;
  await page.route("**/api/history?**", async (route) => {
    const response = await route.fetch();
    fetchedEnd = (await response.json()).latestElapsedMs;
    const before = frames;
    await expect.poll(() => frames).toBeGreaterThan(before + 4);
    await route.fulfill({ response });
  });
  await page.goto("/trends?source=mock");
  const select = page.getByRole("combobox", { name: "분석 시간 범위" });
  await expect(page.locator(".chart-current strong").first()).not.toHaveText(
    "—",
  );
  await select.selectOption("0");
  await expect(
    page.getByText("기록 불러오는 중", { exact: false }),
  ).toHaveCount(0);
  await expect
    .poll(async () =>
      Number(
        await page.locator(".trends-page").getAttribute("data-last-elapsed"),
      ),
    )
    .toBeGreaterThan(fetchedEnd);
  await page.unroute("**/api/history?**");
  await page.route("**/api/history?**", (route) =>
    route.fulfill({ status: 503, body: "unavailable" }),
  );
  await select.selectOption("300");
  await expect(
    page.getByText("기록을 불러오지 못했습니다", { exact: false }),
  ).toBeVisible();
  await page.unroute("**/api/history?**");
  await page.getByRole("button", { name: "다시 시도" }).click();
  await expect(
    page.getByText("기록을 불러오지 못했습니다", { exact: false }),
  ).toHaveCount(0);
  await expect
    .poll(async () =>
      Number(
        await page.locator(".trends-page").getAttribute("data-sample-count"),
      ),
    )
    .toBeGreaterThan(1200);
});

test("switching sources while an old history response is pending never restores old readings", async ({
  page,
}) => {
  let finish: (() => void) | undefined;
  await page.route("**/api/history?**", async (route) => {
    const response = await route.fetch();
    await new Promise<void>((resolve) => {
      finish = resolve;
    });
    await route.fulfill({ response }).catch(() => {});
  });
  await page.goto("/trends?source=mock");
  await expect(page.locator(".chart-current strong").first()).not.toHaveText(
    "—",
  );
  await page
    .getByRole("combobox", { name: "분석 시간 범위" })
    .selectOption("0");
  await expect.poll(() => !!finish).toBe(true);
  await selectSource(page, "csv");
  finish!();
  await page.unroute("**/api/history?**");
  await page
    .getByRole("combobox", { name: "분석 시간 범위" })
    .selectOption("60");
  await expect(page.locator(".analysis-verdict")).toContainText("판정 대기");
  await expect(page.locator(".status-history-segment.fault")).toHaveCount(0);
});

test("one-hour original history remains inspectable", async ({ page }) => {
  test.skip(
    !process.env.DASHBOARD_TEST_HISTORY_MS,
    "Explicit long-history fixture only",
  );
  test.setTimeout(120000);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/trends?source=mock");
  await expect(page.locator(".chart-current strong").first()).not.toHaveText(
    "—",
  );
  const start = Date.now();
  await page
    .getByRole("combobox", { name: "분석 시간 범위" })
    .selectOption("3600");
  await expect
    .poll(
      async () =>
        Number(
          await page.locator(".trends-page").getAttribute("data-sample-count"),
        ),
      { timeout: 90000 },
    )
    .toBeGreaterThan(35000);
  await page
    .getByRole("button", { name: "화면 일시정지", exact: true })
    .click({ timeout: 30000 });
  const frozen = await page
    .locator(".trends-page")
    .getAttribute("data-last-elapsed");
  await page.locator(".chart").first().hover();
  await page.keyboard.down("Control");
  await page.mouse.wheel(0, -300);
  await page.keyboard.up("Control");
  await expect(page.locator(".trends-page")).toHaveAttribute(
    "data-last-elapsed",
    frozen!,
  );
  await page.screenshot({
    path: "../runtime/analysis-history-hour.png",
    fullPage: true,
  });
  console.log(`One-hour load and inspect: ${Date.now() - start}ms`);
  await page
    .getByRole("combobox", { name: "분석 시간 범위" })
    .selectOption("60");
  await expect
    .poll(async () =>
      Number(
        await page.locator(".trends-page").getAttribute("data-sample-count"),
      ),
    )
    .toBeLessThanOrEqual(601);
  expect(errors).toEqual([]);
});

test("reconnection reloads older history instead of replacing it with the 60-second snapshot", async ({
  page,
}) => {
  let cut: (() => void) | undefined;
  let queries = 0;
  page.on("request", (request) => {
    if (request.url().includes("/api/history?")) queries++;
  });
  await page.routeWebSocket("**/ws/telemetry?source=mock", (client) => {
    const server = client.connectToServer();
    cut = () => {
      server.close();
      client.close();
    };
  });
  await page.goto("/trends?source=mock");
  await expect(page.locator(".chart-current strong").first()).not.toHaveText(
    "—",
  );
  await page
    .getByRole("combobox", { name: "분석 시간 범위" })
    .selectOption("0");
  const root = page.locator(".trends-page");
  await expect
    .poll(async () => Number(await root.getAttribute("data-sample-count")))
    .toBeGreaterThan(1200);
  const before = queries;
  cut!();
  await expect.poll(() => queries).toBeGreaterThan(before);
  await expect(
    page.getByText("기록 불러오는 중", { exact: false }),
  ).toHaveCount(0);
  await expect
    .poll(async () => Number(await root.getAttribute("data-sample-count")))
    .toBeGreaterThan(1200);
  await expect(page.locator(".status-history-axis span").first()).toHaveText(
    "0:00",
  );
});
