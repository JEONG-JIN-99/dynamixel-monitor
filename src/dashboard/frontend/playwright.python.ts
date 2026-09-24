import path from "node:path";
import { existsSync } from "node:fs";
// An explicit interpreter also supports a shared development virtual environment.
export function dashboardPython() {
  const local = path.resolve(process.platform === "win32" ? "../.venv/Scripts/python.exe" : "../.venv/bin/python");
  return process.env.DASHBOARD_PYTHON || (existsSync(local) ? local : "python");
}
