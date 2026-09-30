import { dashboardPython } from "./playwright.python";
import { defineConfig } from "@playwright/test";
import path from "node:path";
export default defineConfig({
  testDir: "./e2e-control",
  workers: 1,
  timeout: 45000,
  outputDir: "../runtime/control-browser-results",
  use: {
    baseURL: "http://127.0.0.1:8766",
    headless: true,
    screenshot: "only-on-failure",
  },
  webServer: {
    command: `"${dashboardPython()}" "${path.resolve("../tests/control_browser_server.py")}"`,
    url: "http://127.0.0.1:8766/api/health",
    reuseExistingServer: false,
    timeout: 20000,
  },
});
