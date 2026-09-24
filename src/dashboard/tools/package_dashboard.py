"""Create a clean handoff ZIP with a self-contained dashboard/ root."""
import argparse
import os
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {".venv", "node_modules", "__pycache__", ".pytest_cache", ".git", ".codex", ".agents", "runtime", "test-results", "playwright-report"}

def package(output):
    output = Path(output).resolve()
    if not (ROOT / "frontend/dist/index.html").is_file():
        raise SystemExit("Build the frontend first: cd frontend && npm ci && npm run build")
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "x", compression=ZIP_DEFLATED) as archive:
        for directory, folders, names in os.walk(ROOT):
            folders[:] = sorted(name for name in folders if name not in EXCLUDED and not (Path(directory) / name).is_symlink())
            for name in sorted(names):
                path = Path(directory) / name
                relative = path.relative_to(ROOT)
                if path.is_symlink() or not path.is_file() or path == output:
                    continue
                if path.suffix in {".pyc", ".pyo", ".log", ".zip"} or path.name.startswith(".env"):
                    continue
                archive.write(path, "dashboard/" + relative.as_posix())
        archive.writestr("dashboard/runtime/.gitkeep", "")
    return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "runtime/handoff" / ("dashboard-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".zip"))
    print(package(parser.parse_args().output))
