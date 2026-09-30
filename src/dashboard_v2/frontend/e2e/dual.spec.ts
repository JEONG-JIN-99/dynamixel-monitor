import { test, expect } from "@playwright/test";

test("unsaved settings stay with their motor and page layouts fit on mobile", async ({
  page,
}) => {
  await page.goto("/control?motor=1");
  await expect(page.getByLabel("모터 ID", { exact: true })).toHaveValue("1");
  await page.getByLabel("이동 회전수", { exact: true }).fill("0.75");
  await page.getByRole("combobox", { name: "모터 선택", exact: true }).selectOption("2");
  await expect(page.getByLabel("모터 ID", { exact: true })).toHaveValue("2");
  await page.getByLabel("이동 회전수", { exact: true }).fill("1.25");
  await page.getByRole("combobox", { name: "모터 선택", exact: true }).selectOption("1");
  await expect(page.getByLabel("이동 회전수", { exact: true })).toHaveValue(
    "0.75",
  );
  await page.getByRole("combobox", { name: "모터 선택", exact: true }).selectOption("2");
  await expect(page.getByLabel("이동 회전수", { exact: true })).toHaveValue(
    "1.25",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  for (const name of ["개요", "제어", "모터", "상세 분석", "알림", "로그"]) {
    await page.getByRole("link", { name, exact: true }).click();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
      name,
    ).toBeTruthy();
  }
});

test("two motor control, telemetry, alerts, independent stop and archive replay", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await expect(page.locator(".fleet-row")).toHaveCount(8);
  await expect(page.locator(".chart-card")).toHaveCount(0);
  await expect(page.locator(".sidebar .alert-badge")).toHaveCount(0);
  await page.getByRole("link", { name: "제어", exact: true }).click();
  for (const slot of [1, 2]) {
    await page
      .getByRole("combobox", { name: "모터 선택", exact: true })
      .selectOption(String(slot));
    await expect(page.getByLabel("모터 ID", { exact: true })).toHaveValue(
      String(slot),
    );
    await page.getByLabel("실행 대상", { exact: true }).selectOption("mock");
    await page.getByLabel("가속 시간 (ms)", { exact: true }).fill("100");
    await page.getByLabel("편도 이동 시간 (ms)", { exact: true }).fill("400");
    await page.getByLabel("상단 대기 (초)", { exact: true }).fill("0");
    await page.getByLabel("하단 대기 (초)", { exact: true }).fill("0");
    await page
      .getByLabel("이동 회전수", { exact: true })
      .fill(slot === 1 ? "0.5" : "1");
    await page.getByRole("button", { name: "설정 저장", exact: true }).click();
    await expect(page.getByText("설정 저장됨", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "실험 시작", exact: true }).click();
    await expect(page.locator(".run-state")).toBeVisible();
  }
  const states = await Promise.all(
    [1, 2].map(async (slot) =>
      (await request.get(`/motors/${slot}/api/control`)).json(),
    ),
  );
  expect(states.map((s) => s.active)).toEqual([true, true]);
  expect(states[0].run.runId).not.toBe(states[1].run.runId);
  await page.getByRole("link", { name: "개요", exact: true }).click();
  await expect(
    page.locator('.fleet-row[data-motor="1"] .fleet-state'),
  ).not.toContainText("—");
  await expect(
    page.locator('.fleet-row[data-motor="2"] .fleet-state'),
  ).not.toContainText("—");
  await page.screenshot({ path: "../runtime/v2-overview.png", fullPage: true });
  await page
    .getByRole("link", { name: "모터 2 개요 보기", exact: true })
    .click();
  await expect(page.locator(".overview-grid .chart-card")).toHaveCount(3);
  await expect(page.locator('select[aria-label="모터종류"]')).toContainText(
    "모터 2",
  );
  await page.screenshot({
    path: "../runtime/v2-motor-overview.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "상세 분석", exact: true }).click();
  await page.getByLabel("모터 선택", { exact: true }).selectOption("2");
  await expect(page.locator(".chart-card")).toHaveCount(8);
  await page.getByLabel("분석 시간 범위", { exact: true }).selectOption("300");
  await expect(page.locator(".notice")).toHaveCount(0);
  await page.getByRole("link", { name: "알림", exact: true }).click();
  await expect(page.locator(".motor-alert-section")).toHaveCount(8);
  // Backend-scripted anomalies begin at 20 seconds. The browser stays subscribed to both.
  await expect(
    page.locator('.motor-alert-section[data-motor="1"] .alert-row'),
  ).toHaveCount(1, { timeout: 30000 });
  await expect(
    page.locator('.motor-alert-section[data-motor="2"] .alert-row'),
  ).toHaveCount(1, { timeout: 5000 });
  await expect(page.locator(".sidebar .alert-badge")).toHaveText("2");
  await page.getByRole("combobox", { name: "모터 선택", exact: true }).selectOption("2");
  await expect(page.locator(".motor-alert-section")).toHaveCount(1);
  await expect(page.locator(".motor-alert-section")).toHaveAttribute(
    "data-motor",
    "2",
  );
  await page.getByRole("button", { name: "전체 확인", exact: true }).click();
  await expect(page.locator(".sidebar .alert-badge")).toHaveText("1");
  await expect(page.getByRole("button", { name: "전체 확인", exact: true })).toBeDisabled();
  await page.getByRole("combobox", { name: "모터 선택", exact: true }).selectOption("all");
  await page.getByRole("button", { name: "전체 확인", exact: true }).click();
  await expect(page.locator(".sidebar .alert-badge")).toHaveCount(0);
  await expect(page.locator('.alert-row[data-read="true"]')).toHaveCount(2);
  await expect(page.locator('.alert-row[data-active="true"]')).toHaveCount(2);
  await expect(page.getByRole("button", { name: "전체 확인", exact: true })).toBeDisabled();
  await page.screenshot({ path: "../runtime/v2-alerts.png", fullPage: true });
  await page.getByRole("link", { name: "개요", exact: true }).click();
  await page
    .locator('.fleet-row[data-motor="1"]')
    .getByRole("button", { name: "모터 1 종료", exact: true })
    .click();
  await expect(
    page.locator('.fleet-row[data-motor="1"] .fleet-state'),
  ).toContainText("전원 꺼짐");
  await expect(
    page.getByRole("button", { name: "모터 2 종료", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "로그", exact: true }).click();
  await page.getByLabel("모터 선택", { exact: true }).selectOption("1");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page.getByRole("link", { name: "기록 보기 →" }).click();
  await expect(page.locator(".chart-card")).toHaveCount(8);
  await expect(page.locator(".notice")).toHaveCount(0);
  await page.screenshot({
    path: "../runtime/v2-log-replay.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "개요", exact: true }).click();
  await page
    .locator('.fleet-row[data-motor="1"]')
    .getByRole("button", { name: "모터 1 시작", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "모터 1 종료", exact: true }),
  ).toBeVisible();
  const restarted = await (await request.get("/motors/1/api/control")).json();
  expect(restarted.run.runId).not.toBe(states[0].run.runId);
  expect(
    (await (await request.get("/motors/2/api/control")).json()).run.runId,
  ).toBe(states[1].run.runId);
  for (const slot of [1, 2]) {
    const s = await (await request.get(`/motors/${slot}/api/control`)).json();
    await request.post(`/motors/${slot}/api/control/stop`, {
      data: { runId: s.run.runId },
    });
  }
  await expect(
    page.locator('.fleet-row[data-motor="2"] .fleet-state'),
  ).toContainText("전원 꺼짐");
  await page.reload();
  await expect(page.locator(".sidebar .alert-badge")).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
});
