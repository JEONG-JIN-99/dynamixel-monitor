import { defineConfig } from "@playwright/test";
import { dashboardPython } from "./playwright.python";
import path from "node:path";
export default defineConfig({
  testDir: "./e2e",
  testMatch: ["dual.spec.ts", "fleet.spec.ts", "motors.spec.ts"],
  workers: 1,
  timeout: 70000,
  outputDir: "../runtime/dual-browser-results",
  use: {
    baseURL: "http://127.0.0.1:8767",
    headless: true,
    screenshot: "only-on-failure",
  },
  webServer: {
    command: `"${dashboardPython()}" "${path.resolve("../backend/tests/dual_browser_server.py")}"`,
    url: "http://127.0.0.1:8767/api/health",
    reuseExistingServer: false,
    timeout: 20000,
  },
});
