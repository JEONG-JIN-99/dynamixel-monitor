import { test, expect } from "@playwright/test";

test("six virtual motors have distinct telemetry, independent controls and motor drill-down", async ({
  page,
  request,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const runs: Record<number, string> = {};
  for (let slot = 3; slot <= 8; slot++) {
    const state = await (
      await request.get(`/motors/${slot}/api/control`)
    ).json();
    expect(state.allowedSources).toEqual(["mock"]);
    await request.post(`/motors/${slot}/api/control/config`, {
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
    });
  }
  await page.setViewportSize({ width: 1440, height: 1100 });
  await page.goto("/");
  await expect(page.getByRole('button', { name: '3D 모델', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('.quadruped-canvas')).toHaveAttribute('data-ready', 'true');
  await page.getByRole('button', { name: '도면', exact: true }).click();
  await expect(page.locator(".fleet-marker")).toHaveCount(8);
  await expect(page.locator('.explorer-drawing')).toBeVisible();
  await expect(page.locator('.explorer-callout')).toHaveCount(8);
  await page.getByRole('button', { name: /^모터 2, 왼쪽 앞다리 무릎/ }).click();
  await expect(page.locator('.fleet-row[data-motor="2"]')).toHaveClass(/picked/);
  await expect(page.locator('.explorer-roles')).toContainText('다리 굽힘·폄');
  await expect(page.locator(".chart-card")).toHaveCount(0);
  await expect(page.locator('.fleet-row[data-motor="8"]')).toContainText(
    "전원 꺼짐",
  );
  for (let slot = 3; slot <= 8; slot++) {
    await page
      .getByRole("button", { name: `모터 ${slot} 시작`, exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: `모터 ${slot} 종료`, exact: true }),
    ).toBeEnabled();
    runs[slot] = (
      await (await request.get(`/motors/${slot}/api/control`)).json()
    ).run.runId;
  }
  expect(new Set(Object.values(runs)).size).toBe(6);
  await expect(
    page.locator('.fleet-row[data-motor="8"] .fleet-state'),
  ).toContainText("켜짐");
  await page
    .getByRole("link", { name: "모터 8 개요 보기", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "모터 8 개요" }),
  ).toBeVisible();
  await expect(page.locator(".overview-grid .chart-card")).toHaveCount(3);
  await expect(page.getByRole("combobox", { name: "모터종류", exact: true })).toContainText(
    "모터 8",
  );
  await page.getByRole("link", { name: "상세 분석", exact: true }).click();
  await expect(page.getByLabel("모터 선택", { exact: true })).toHaveValue("8");
  await expect(page.locator(".chart-card")).toHaveCount(8);
  await page.getByRole("link", { name: "모터", exact: true }).click();
  await expect(page.getByLabel("모터 선택", { exact: true })).toHaveValue("8");
  await page.getByRole("link", { name: "제어", exact: true }).click();
  await expect(page.getByLabel("실행 대상").locator("option")).toHaveCount(1);
  await page.getByRole("link", { name: "개요", exact: true }).click();
  await page.getByRole('button', { name: '도면', exact: true }).click();
  await expect(
    page.locator('.fleet-row[data-motor="3"] .fleet-state'),
  ).toContainText("마찰", { timeout: 18000 });
  await expect(page.locator(".fleet-marker.fault")).not.toHaveCount(0);
  for (const viewport of [{ width: 1920, height: 1080 }, { width: 1366, height: 768 }]) {
    await page.setViewportSize(viewport);
    await expect.poll(() => page.evaluate(() => ({
      pageFits: document.documentElement.scrollHeight <= innerHeight + 1,
      panelsFit: [...document.querySelectorAll('.fleet-robot, .fleet-list')].every(el => el.getBoundingClientRect().bottom <= innerHeight),
      lastMotorVisible: document.querySelector('.fleet-row[data-motor="8"]')!.getBoundingClientRect().bottom <= innerHeight,
    }))).toEqual({ pageFits: true, panelsFit: true, lastMotorVisible: true });
  }
  await page.screenshot({
    path: "../runtime/fleet-overview.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "3D 모델", exact: true }).click();
  const model = page.locator('.quadruped-canvas');
  await expect(model).toHaveAttribute('data-ready', 'true');
  await expect(page.locator('.quadruped-label')).toHaveCount(8);
  await expect(page.locator('.quadruped-label.fault')).not.toHaveCount(0);
  await page.getByRole('button', { name: /^3D 모터 6 선택/ }).click();
  await expect(page.locator('.fleet-row[data-motor="6"]')).toHaveClass(/picked/);
  const before = await model.getAttribute('data-camera');
  const bounds = (await model.boundingBox())!;
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height * .8);
  await page.mouse.down();
  await page.mouse.move(bounds.x + bounds.width * .75, bounds.y + bounds.height * .75, { steps: 10 });
  await page.mouse.up();
  await expect(model).not.toHaveAttribute('data-camera', before!);
  const dragged = await model.getAttribute('data-camera');
  await page.mouse.wheel(0, -180);
  await expect(model).not.toHaveAttribute('data-camera', dragged!);
  await page.getByRole('button', { name: '처음 시점', exact: true }).click();
  await page.getByRole('button', { name: '자동 회전', exact: true }).click();
  await expect(page.getByRole('button', { name: '자동 회전', exact: true })).toHaveAttribute('aria-pressed', 'true');
  const orbit = await model.getAttribute('data-camera');
  await expect(model).not.toHaveAttribute('data-camera', orbit!);
  await page.getByRole('button', { name: '처음 시점', exact: true }).click();
  expect(await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight + 1)).toBe(true);
  await page.screenshot({ path: '../runtime/fleet-3d.png', fullPage: true });
  await page.getByRole('button', { name: '도면', exact: true }).click();
  await expect(page.locator('.fleet-marker')).toHaveCount(8);
  await page.getByRole("button", { name: "모터 5 종료", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "모터 5 시작", exact: true }),
  ).toBeEnabled();
  await expect(
    page.locator('.fleet-row[data-motor="5"] .fleet-state'),
  ).toContainText("전원 꺼짐");
  await expect(page.locator(".fleet-marker.off")).not.toHaveCount(0);
  // Stop during a fault: the current overview clears it, the recording keeps it.
  await page.getByRole("button", { name: "모터 3 종료", exact: true }).click();
  await expect(page.getByRole("button", { name: "모터 3 시작", exact: true })).toBeEnabled();
  const stopped = page.locator('.fleet-row[data-motor="3"] .fleet-state');
  await expect(stopped).toContainText("전원 꺼짐");
  await expect(stopped).not.toContainText("마찰");
  const recorded = await (await request.get(`/motors/3/api/runs/${runs[3]}/history`)).json();
  expect(recorded.samples.some((s: { diagnosis: { state: string } }) => s.diagnosis.state === "fault")).toBe(true);
  expect(
    (await (await request.get("/motors/8/api/control")).json()).active,
  ).toBe(true);
  await page.getByRole("link", { name: "로그", exact: true }).click();
  await page.getByLabel("모터 선택", { exact: true }).selectOption("5");
  await page.getByRole("link", { name: "기록 보기 →" }).first().click();
  await expect(page.locator(".chart-card")).toHaveCount(8);
  await expect(page.locator(".notice")).toHaveCount(0);
  for (const slot of [4, 6, 7, 8])
    await request.post(`/motors/${slot}/api/control/stop`, {
      data: { runId: runs[slot] },
    });
  await page.getByRole("link", { name: "개요", exact: true }).click();
  await page.getByRole('button', { name: '도면', exact: true }).click();
  await page.setViewportSize({ width: 768, height: 1024 });
  expect(
    await page
      .locator(".fleet-robot")
      .evaluate((el) => el.getBoundingClientRect().right),
  ).toBeLessThanOrEqual(
    await page
      .locator(".fleet-list")
      .evaluate((el) => el.getBoundingClientRect().left),
  );
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../runtime/fleet-mobile.png",
    fullPage: true,
  });
  await page.getByRole('button', { name: '3D 모델', exact: true }).click();
  await expect(page.locator('.quadruped-canvas')).toHaveAttribute('data-ready', 'true');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: '../runtime/fleet-3d-mobile.png', fullPage: true });
  expect(errors).toEqual([]);
});
