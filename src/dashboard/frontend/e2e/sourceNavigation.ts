import type { Page } from "@playwright/test";
// Source selection is an integration URL option, no longer a dashboard control.
export async function selectSource(page: Page, source: "csv" | "mock") {
  await page.evaluate((source) => {
    const url = new URL(location.href);
    url.searchParams.set("source", source);
    history.pushState(
      {
        ...history.state,
        current: url.pathname + url.search,
        position: (history.state?.position ?? 0) + 1,
      },
      "",
      url,
    );
    dispatchEvent(new PopStateEvent("popstate", { state: history.state }));
  }, source);
}
