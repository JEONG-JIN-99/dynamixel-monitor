import { test, expect } from "@playwright/test";
test("53 registers, tabs, search, order and source changes", async ({
  page,
}) => {
  await page.goto("/?source=mock");
  await page.getByRole("link", { name: "모터", exact: true }).click();
  await expect(page).toHaveURL(/motors\?source=mock/);
  await expect(page.locator(".register-table tbody tr")).toHaveCount(53);
  await expect(page.locator(".provided-count")).toHaveText("값 제공 53 / 53개");
  await page.getByRole("button", { name: "EEPROM 22", exact: true }).click();
  await expect(page.locator(".register-table tbody tr")).toHaveCount(22);
  await page.getByRole("button", { name: "RAM 31", exact: true }).click();
  await expect(page.locator(".register-table tbody tr")).toHaveCount(31);
  await page
    .getByRole("searchbox", { name: "주소 또는 항목명 검색" })
    .fill("Present Current");
  await expect(page.locator(".register-table tbody tr")).toHaveCount(1);
  await expect(
    page.locator("tr[data-address='126'] .register-raw"),
  ).not.toHaveText("—");
  await page
    .getByRole("searchbox", { name: "주소 또는 항목명 검색" })
    .fill("없는항목");
  await expect(page.locator(".register-empty")).toContainText("검색 조건");
  await page.getByRole("searchbox", { name: "주소 또는 항목명 검색" }).fill("");
  await page.getByRole("combobox", { name: "주소 정렬" }).selectOption("desc");
  await expect(
    page.locator(".register-table tbody tr").first(),
  ).toHaveAttribute("data-address", "147");
  await page.getByRole("button", { name: "실험 CSV로 돌아가기" }).click();
  await expect(page.getByRole("button", { name: "실험 CSV로 돌아가기" })).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("tr[data-address='126'] .register-raw")).toHaveText(
    "—",
  );
  await expect(
    page.locator("tr[data-address='126'] .register-status"),
  ).toHaveText("변환값 수신");
  await expect(
    page.locator("tr[data-address='116'] .register-status"),
  ).toHaveText("명령 기록");
  await page.getByRole("button", { name: "EEPROM 22", exact: true }).click();
  await expect(page.locator("tr[data-address='8'] .register-value")).toHaveText(
    "—",
  );
  await page.reload();
  await expect(page.locator(".register-table tbody tr")).toHaveCount(53);
});
test("pause freezes table values, resume catches up, source switch clears frozen mock", async ({
  page,
}) => {
  let frames = 0;
  page.on("websocket", (socket) =>
    socket.on("framereceived", ({ payload }) => {
      if (JSON.parse(String(payload)).type === "samples") frames++;
    }),
  );
  await page.goto("/motors?source=mock");
  await expect(page.locator(".connection-badge")).toContainText("서버 수신");
  await expect.poll(() => frames).toBeGreaterThan(0);
  const beforeFrames = frames;
  await page
    .getByRole("button", { name: "화면 일시정지", exact: true })
    .click();
  const raw = page.locator("tr[data-address='120'] .register-raw");
  const before = await raw.textContent();
  await expect.poll(() => frames).toBeGreaterThan(beforeFrames + 2);
  await expect(raw).toHaveText(before!);
  await page.getByRole("button", { name: "화면 재개", exact: true }).click();
  await expect(raw).not.toHaveText(before!);
  await page
    .getByRole("button", { name: "화면 일시정지", exact: true })
    .click();
  await page.getByRole("button", { name: "실험 CSV로 돌아가기" }).click();
  await expect(
    page.getByRole("button", { name: "화면 일시정지", exact: true }),
  ).toHaveAttribute("aria-pressed", "false");
  await expect(page.locator("tr[data-address='2'] .register-value")).toHaveText(
    "—",
  );
});
for (const width of [1920, 1440, 390]) {
  test(`motor table layout ${width}`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.setViewportSize({ width, height: width === 1920 ? 1080 : 900 });
    await page.goto("/motors?source=mock");
    await page.getByRole("button", { name: "RAM 31", exact: true }).click();
    await page.locator("tr[data-address='126']").scrollIntoViewIfNeeded();
    await page
      .getByRole("button", { name: "화면 일시정지", exact: true })
      .click();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: `../runtime/motors-${width}.png`,
      fullPage: true,
    });
    expect(errors).toEqual([]);
  });
}
