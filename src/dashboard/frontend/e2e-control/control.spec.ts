import { test, expect } from "@playwright/test";
test("idle → save → run → finish cycle → log → independent replay", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.setViewportSize({ width: 1440, height: 1050 });
  await page.goto("/control");
  await expect(
    page.getByRole("button", { name: "실험 시작", exact: true }),
  ).toBeDisabled();
  expect((await (await request.get("/api/runs")).json()).total).toBe(0);
  await page
    .getByLabel("모터 종류", { exact: true })
    .selectOption("XM430-W350");
  await page.getByLabel("모터 ID", { exact: true }).fill("3");
  await page.getByLabel("가속 시간 (ms)", { exact: true }).fill("200");
  await page.getByLabel("편도 이동 시간 (ms)", { exact: true }).fill("1000");
  await page.getByLabel("상단 대기 (초)", { exact: true }).fill("0.2");
  await page.getByLabel("하단 대기 (초)", { exact: true }).fill("0.2");
  await page.getByRole("button", { name: "설정 저장", exact: true }).click();
  await expect(page.getByText("설정 저장됨", { exact: true })).toBeVisible();
  expect((await (await request.get("/api/runs")).json()).total).toBe(0);
  await page.screenshot({
    path: "../runtime/control-desktop.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "실험 시작", exact: true }).click();
  await expect(page).toHaveURL(/source=mock/);
  await expect(page.locator(".run-state>span")).toHaveText("실험 중");
  const state = await (await request.get("/api/control")).json();
  const runId = state.run.runId;
  expect(
    (
      await request.post("/api/control/start", {
        data: { configId: state.saved.id },
      })
    ).status(),
  ).toBe(409);
  await page.reload();
  await expect(page.locator(".run-state>span")).toHaveText("실험 중");
  await page.getByRole("link", { name: "개요", exact: true }).click();
  await expect(page.getByRole("combobox", { name: "모터종류", exact: true })).toHaveValue("XM430-W350:3");
  await page.getByRole("button", { name: "실험 종료", exact: true }).click();
  await expect(page.locator(".run-state>span")).toHaveText("왕복 완료 후 종료");
  await expect(page.locator(".run-state>span")).toHaveText("완료", {
    timeout: 7000,
  });
  await page.getByRole("link", { name: "로그", exact: true }).click();
  await expect(page.getByRole("link", { name: "기록 보기 →" })).toHaveCount(1);
  await page.screenshot({
    path: "../runtime/logs-desktop.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "기록 보기 →" }).click();
  await expect(
    page.getByRole("heading", { name: "실험 기록", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("combobox", { name: "분석 시간 범위" }),
  ).toHaveValue("0");
  await expect
    .poll(() => page.locator(".trends-page").getAttribute("data-sample-count"))
    .not.toBe("0");
  const count = await page
    .locator(".trends-page")
    .getAttribute("data-sample-count");
  const latest = await page
    .locator(".trends-page")
    .getAttribute("data-last-elapsed");
  await expect(
    page
      .locator(".trends-page")
      .getByText("데이터가 없습니다", { exact: true }),
  ).toHaveCount(0);
  // A new active run must not enter the archived graph.
  await request.post("/api/control/start", {
    data: { configId: state.saved.id },
  });
  await page.waitForTimeout(1300);
  expect(
    await page.locator(".trends-page").getAttribute("data-sample-count"),
  ).toBe(count);
  expect(
    await page.locator(".trends-page").getAttribute("data-last-elapsed"),
  ).toBe(latest);
  await page.reload();
  await expect
    .poll(() => page.locator(".trends-page").getAttribute("data-sample-count"))
    .toBe(count);
  await page.screenshot({
    path: "../runtime/recorded-analysis-desktop.png",
    fullPage: true,
  });
  const newState = await (await request.get("/api/control")).json();
  expect(newState.run.runId).not.toBe(runId);
  await request.post("/api/control/stop", {
    data: { runId: newState.run.runId },
  });
  await expect
    .poll(
      async () => (await (await request.get("/api/control")).json()).active,
      { timeout: 7000 },
    )
    .toBe(false);
  await page
    .getByRole("combobox", { name: "분석 시간 범위" })
    .selectOption("300");
  await expect
    .poll(() => page.locator(".trends-page").getAttribute("data-sample-count"))
    .toBe(count);
  expect(errors).toEqual([]);
});
for (const width of [390, 900])
  test(`control and logs fit ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    for (const view of ["control", "logs"]) {
      await page.goto(`/${view}`);
      await expect(
        page.getByRole("heading", {
          name: view === "control" ? "제어" : "로그",
          exact: true,
        }),
      ).toBeVisible();
      await expect
        .poll(() =>
          page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
        )
        .toBe(true);
      await page.screenshot({
        path: `../runtime/${view}-${width}.png`,
        fullPage: true,
      });
    }
  });
