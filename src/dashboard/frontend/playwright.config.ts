import { defineConfig } from "@playwright/test";
import path from "node:path";
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  timeout: 30000,
  outputDir: "../runtime/browser-results",
  use: {
    baseURL: "http://127.0.0.1:8765",
    headless: true,
    screenshot: "only-on-failure",
  },
  webServer: {
    command:
      process.platform === "win32"
        ? `"${path.resolve("../../../.venv/Scripts/python.exe")}" "${path.resolve("../tests/browser_server.py")}"`
        : "../../../.venv/bin/python ../tests/browser_server.py",
    url: "http://127.0.0.1:8765/api/health",
    reuseExistingServer: false,
    timeout: 20000,
  },
});
