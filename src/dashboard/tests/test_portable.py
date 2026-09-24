"""Verify the actual handoff ZIP after extraction outside the project tree."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from zipfile import ZipFile

from websockets.sync.client import connect
from motor_dashboard.tools.package_dashboard import package


def test_clean_handoff_runs_outside_repository(tmp_path):
    archive_path = package(tmp_path / "handoff.zip")
    with ZipFile(archive_path) as archive:
        assert "dashboard/frontend/dist/index.html" in archive.namelist()
        assert "dashboard/request.md" in archive.namelist()
        assert not any("/node_modules/" in n or "/.venv/" in n or n.endswith(".csv") for n in archive.namelist())
        assert [n for n in archive.namelist() if "/runtime/" in n] == ["dashboard/runtime/.gitkeep"]
        archive.extractall(tmp_path / "isolated")
    root = tmp_path / "isolated/dashboard"
    # Renaming catches implicit dependence on the folder being called dashboard.
    renamed = root.with_name("motor demo")
    root.rename(renamed)
    root = renamed
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    config = root / "config/dashboard.toml"
    config.write_text(config.read_text(encoding="utf-8").replace("port = 8000", f"port = {port}"), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME"}}
    base = f"http://127.0.0.1:{port}"

    def api(path, body=None):
        request = Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=3) as reply:
            return json.load(reply)

    def wait_for(fn):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                value = fn()
                if value:
                    return value
            except (OSError, ValueError):
                pass
            time.sleep(.05)
        raise AssertionError("Portable server did not reach expected state")

    with (tmp_path / "server.log").open("w") as log:
        process = subprocess.Popen([sys.executable, str(root / "main.py")], cwd=tmp_path,
                                   env=env, stdout=log, stderr=log)
        try:
            wait_for(lambda: api("/api/health")["ok"])
            assert not api("/api/control")["active"]
            assert api("/api/runs")["total"] == 0
            with urlopen(base) as reply:
                assert 'id="app"' in reply.read().decode()
            config_values = api("/api/control")["defaults"]
            config_values.update(acceleration_ms=100, profile_duration_ms=400,
                                 top_dwell_sec=0, bottom_dwell_sec=0, max_cycles=0)
            saved = api("/api/control/config", {"source":"mock", "config":config_values})["saved"]
            started = api("/api/control/start", {"configId":saved["id"]})
            run = started["run"]["runId"]
            with connect(f"ws://127.0.0.1:{port}/ws/telemetry?source=mock") as ws:
                snapshot = json.loads(ws.recv(timeout=5))
                assert snapshot["type"] == "snapshot"
                sample = None
                for _ in range(30):
                    message = json.loads(ws.recv(timeout=5))
                    if message["type"] == "samples":
                        sample = message["samples"][0]
                        break
                assert sample and len(sample["registers"]) == 53
                assert sample["basePosition"] == 100
                history = api(f"/api/history?source=mock&runId={run}&sourceSessionId={sample['sourceSessionId']}&durationSec=0")
                assert next(s for s in history["samples"] if s["seq"] == sample["seq"]) == sample
            api("/api/control/stop", {"runId":run})
            wait_for(lambda: not api("/api/control")["active"])
            record = api(f"/api/runs/{run}")
            assert record["status"] == "completed"
            replay = api(f"/api/runs/{run}/history?durationSec=0")
            assert replay["samples"] and all(s["basePosition"] == 100 for s in replay["samples"])
            assert list((root / "runtime/mock_runs").glob("*/*/*/*/telemetry.csv"))
            assert not (tmp_path / "results").exists()
        finally:
            process.terminate()
            process.wait(timeout=10)
        # Reopening discovers saved history without restarting an experiment.
        process = subprocess.Popen([sys.executable, str(root / "main.py")], cwd=tmp_path,
                                   env=env, stdout=log, stderr=log)
        try:
            wait_for(lambda: api("/api/health")["ok"])
            assert not api("/api/control")["active"]
            assert api("/api/runs")["total"] == 1
            assert api(f"/api/runs/{run}/history?durationSec=0")["samples"]
        finally:
            process.terminate()
            process.wait(timeout=10)
