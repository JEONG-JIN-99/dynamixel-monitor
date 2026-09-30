import { test, expect } from "@playwright/test";

test.beforeEach(async ({ request }) => {
  const state = await (await request.get("/motors/8/api/control")).json();
  const saved = await (
    await request.post("/motors/8/api/control/config", {
      data: {
        source: "mock",
        config: {
          ...state.saved.config,
          profile_duration_ms: 400,
          acceleration_ms: 100,
          top_dwell_sec: 0,
          bottom_dwell_sec: 0,
        },
      },
    })
  ).json();
  const response = await request.post("/motors/8/api/control/start", {
    data: { configId: saved.saved.id },
  });
  expect(response.ok()).toBe(true);
});
test.afterEach(async ({ request }) => {
  const state = await (await request.get("/motors/8/api/control")).json();
  if (state.active) {
    await request.post("/motors/8/api/control/stop", {
      data: { runId: state.run.runId },
    });
    await expect
      .poll(
        async () =>
          (await (await request.get("/motors/8/api/control")).json()).active,
      )
      .toBe(false);
  }
});

test("five change-cause categories cover 53 registers; search crosses categories; sorting and memory details", async ({
  page,
}) => {
  await page.goto("/motors?motor=8");
  const rows = page.locator(".register-table tbody tr[data-address]");
  await expect(
    page.getByRole("button", { name: "동작·오류 상태값 12", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(rows).toHaveCount(12);
  await expect(rows.first()).toHaveAttribute("data-address", "132");
  await expect(page.locator(".provided-count")).toHaveText("값 제공 53 / 53개");
  const addresses: string[] = [];
  for (const [label, count] of [
    ["제어·설정값", 34],
    ["설정·자동 변경값", 2],
    ["식별값", 3],
    ["동작·오류 상태값", 12],
    ["명령 처리 결과값", 2],
  ] as const) {
    await page
      .getByRole("button", { name: `${label} ${count}`, exact: true })
      .click();
    await expect(rows).toHaveCount(count);
    await expect(page.locator(".register-row-count")).toHaveText(
      `표시 ${count} / ${count}개`,
    );
    addresses.push(
      ...(await rows.evaluateAll((items) =>
        items.map((item) => item.getAttribute("data-address")!),
      )),
    );
  }
  expect(addresses).toHaveLength(53);
  expect(new Set(addresses).size).toBe(53);
  const search = page.getByRole("searchbox", { name: "주소 또는 항목명 검색" });
  await search.fill("Present Current");
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toHaveAttribute("data-address", "126");
  await expect(
    page.getByRole("button", { name: "전체 53", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator(".register-detail strong")).toContainText("RAM");
  await expect(page.locator(".register-row-count")).toHaveText("표시 1 / 53개");
  await search.fill("없는항목");
  await expect(page.locator(".register-empty")).toContainText("검색 조건");
  await search.fill("");
  await expect(
    page.getByRole("button", { name: "명령 처리 결과값 2", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(rows).toHaveCount(2);
  await search.fill("원점");
  await expect(rows.first()).toHaveAttribute("data-address", "20");
  await expect(page.locator(".register-detail strong")).toContainText("EEPROM");
  await page
    .getByRole("button", { name: "제어·설정값 34", exact: true })
    .click();
  await expect(search).toHaveValue("");
  await expect(rows).toHaveCount(34);
  await page.getByRole("button", { name: "전체 53", exact: true }).click();
  await expect(rows).toHaveCount(53);
  await page.getByLabel("항목 정렬").selectOption("desc");
  await expect(rows.first()).toHaveAttribute("data-address", "147");
  await page.getByLabel("항목 정렬").selectOption("asc");
  await expect(rows.first()).toHaveAttribute("data-address", "0");
  await page.reload();
  await expect(rows).toHaveCount(12);
  await expect(rows.first()).toHaveAttribute("data-address", "132");
});

test("pause freezes readings across categories and motor switch clears frozen readings", async ({
  page,
}) => {
  let frames = 0;
  let motor7Tick: string | undefined;
  page.on("websocket", (socket) =>
    socket.on("framereceived", ({ payload }) => {
      const message = JSON.parse(String(payload));
      if (message.type === "samples") frames++;
      if (
        socket.url().includes("/motors/7/ws/") &&
        (message.type === "snapshot" || message.type === "reset")
      ) {
        // A preceding fleet test may leave completed motor 7 readings in the server.
        // Switching must show that motor's snapshot, rather than motor 8's frozen data.
        motor7Tick = message.latest?.registers?.["120"]?.raw?.toLocaleString("ko-KR") ?? "—";
      }
    }),
  );
  await page.goto("/motors?motor=8");
  const raw = page.locator("tr[data-address='120'] .register-raw");
  await expect(raw).not.toHaveText("—");
  await expect.poll(() => frames).toBeGreaterThan(0);
  await page
    .getByRole("button", { name: "화면 일시정지", exact: true })
    .click();
  const before = await raw.textContent();
  const beforeFrames = frames;
  await page
    .getByRole("button", { name: "제어·설정값 34", exact: true })
    .click();
  await expect.poll(() => frames).toBeGreaterThan(beforeFrames + 2);
  await page
    .getByRole("button", { name: "동작·오류 상태값 12", exact: true })
    .click();
  await expect(raw).toHaveText(before!);
  await page.getByRole("button", { name: "화면 재개", exact: true }).click();
  await expect(raw).not.toHaveText(before!);
  await page
    .getByRole("button", { name: "화면 일시정지", exact: true })
    .click();
  await page.getByLabel("모터 선택", { exact: true }).selectOption("7");
  await expect(
    page.getByRole("button", { name: "화면 일시정지", exact: true }),
  ).toHaveAttribute("aria-pressed", "false");
  await expect.poll(() => motor7Tick).toBeDefined();
  await expect(raw).toHaveText(motor7Tick!);
});

for (const width of [1920, 1440, 390]) {
  test(`motor categories layout ${width}`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.setViewportSize({ width, height: width === 1920 ? 1080 : 900 });
    await page.goto("/motors?motor=8");
    await expect(page.locator(".provided-count")).toHaveText(
      "값 제공 53 / 53개",
    );
    await page
      .getByRole("button", { name: "화면 일시정지", exact: true })
      .click();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const buttons = await page
      .locator(".register-tabs button")
      .evaluateAll((items) =>
        items.map((item) => {
          const r = item.getBoundingClientRect();
          return { left: r.left, right: r.right };
        }),
      );
    for (const button of buttons) {
      expect(button.left).toBeGreaterThanOrEqual(0);
      expect(button.right).toBeLessThanOrEqual(width);
    }
    await page.screenshot({
      path: `../runtime/motors-categories-${width}.png`,
      fullPage: true,
    });
    expect(errors).toEqual([]);
  });
}
