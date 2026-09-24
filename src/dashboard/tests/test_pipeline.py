import asyncio
import csv
from dataclasses import replace
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from motor_dashboard.buffer import SampleBuffer
from motor_dashboard.csv_reader import CsvTail
from motor_dashboard.file_lock import FileLock, is_locked
from motor_dashboard.main import create_app
from motor_dashboard.normalize import normalize
from motor_dashboard.settings import Settings
from motor_dashboard.source_manager import SourceManager
from motor_dashboard.stream import TelemetryHub
from motor_dashboard.experiment.configuration import load_config, PROJECT_ROOT
from motor_dashboard.experiment.run_manifest import RunManifest


def row(t=0, **changes):
    result = {"PC Time": "2026-09-22T12:00:00.123", "Elapsed Time [s]": str(t),
              "Motor Model": "XM430-W210", "Motor ID": "1", "Hardware Error Status": "0",
              "Moving": "1", "Moving Status": "2", "Present PWM": "-10",
              "Present Current": "-100", "Present Current [mA]": "-269",
              "Present Velocity": "-20", "Present Position": "-4096",
              "Velocity Trajectory": "-20", "Position Trajectory": "-4000",
              "Goal Position": "-5000", "Present Input Voltage": "120",
              "Present Temperature": "31", "Cycle": "1", "Phase": "UP_ACCEL",
              "Condition": "normal", "Realtime Tick": "123"}
    result.update(changes)
    return result


def csv_bytes(rows, header=True):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=list(row()))
    if header:
        writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8-sig" if header else "utf-8")


def setup_source(tmp_path, rows=None, status="completed"):
    path = tmp_path / "sample.csv"
    path.write_bytes(csv_bytes(rows if rows is not None else [row()]))
    meta = tmp_path / "sample.json"
    meta.write_text(json.dumps({"created_at": "2026-09-22T12:00:00+09:00", "settings": {"baudrate": 57600}}))
    manifest = {"schemaVersion": 1, "runId": "run-1", "status": status,
                "csvPath": str(path), "metadataPath": str(meta),
                "motorModel": "XM430-W210", "motorId": 1,
                "sampleIntervalSec": 0.1, "flushEveryRows": 20,
                "startedAt": "2026-09-22T12:00:00+09:00", "error": None}
    manifest_path = tmp_path / "current_experiment.json"
    manifest_path.write_text(json.dumps(manifest))
    settings = Settings(manifest_path=manifest_path, data_root=tmp_path, mock_data_root=tmp_path / "mock_runs", poll_interval_sec=0.02)
    return settings, manifest, path


def test_units_identity_time_and_no_double_sign():
    sample = normalize(row(), {"runId": "x", "motorModel": "XM430-W210", "motorId": 1},
                       {"created_at": "2026-09-22T12:00:00+09:00"}, 1, "server", "source")
    assert sample["current"] == pytest.approx(-0.269)
    assert sample["position"] == -4096
    assert sample["pwm"] == pytest.approx(-1.13)
    assert sample["velocity"] == pytest.approx(-4.58)
    assert sample["voltage"] == 12
    assert sample["goalSource"] == "command"
    assert sample["timestamp"] == datetime(2026, 9, 22, 3, 0, 0, 123000, tzinfo=timezone.utc).timestamp() * 1000
    sample = normalize(row(**{"PC Time": "invalid"}), {"runId": "x", "motorModel": "XM430-W210", "motorId": 1},
                       {}, 1, "s", "x")
    assert sample["timestamp"] is None and sample["pcTime"] == "invalid"


def test_xl_load_is_not_current():
    r = row(**{"Motor Model": "XL430-W250", "Present Load": "-30"})
    r.pop("Present Current")
    s = normalize(r, {"runId": "x", "motorModel": "XL430-W250", "motorId": 1}, {}, 1, "s", "x")
    assert s["current"] is None and s["loadPercent"] == -3


@pytest.mark.parametrize("column,value", [("Moving", "2"), ("Present PWM", "65535"), ("Elapsed Time [s]", "nan"), ("Motor ID", "2")])
def test_invalid_rows_rejected(column, value):
    with pytest.raises(ValueError):
        normalize(row(**{column: value}), {"runId": "x", "motorModel": "XM430-W210", "motorId": 1}, {}, 1, "s", "x")


def test_tail_bom_utf8_quoted_newline_and_partial_record(tmp_path):
    path = tmp_path / "s.csv"
    data = csv_bytes([row(**{"Phase": '위쪽\n"hold", waiting'})])
    path.write_bytes(b"")
    tail = CsvTail(path)
    records = []
    # Split every byte, including the BOM, Korean UTF-8 and escaped quotes.
    for byte in data:
        with path.open("ab") as out:
            out.write(bytes([byte]))
        records.extend(tail.poll(chunk_size=1)[0])
    assert len(records) == 1 and records[0][1]["Phase"] == '위쪽\n"hold", waiting'
    assert tail.poll()[0] == []
    second = csv_bytes([row(0.1)], header=False)
    with path.open("ab") as out:
        out.write(second[:-3])
    assert tail.poll()[0] == []
    with path.open("ab") as out:
        out.write(second[-3:])
    assert tail.poll()[0][0][0] == 2


def test_final_record_without_newline_and_malformed_sequence(tmp_path):
    path = tmp_path / "s.csv"
    path.write_bytes(csv_bytes([row()]) + b"bad,row\r\n" + csv_bytes([row(1)], False).rstrip(b"\r\n"))
    tail = CsvTail(path)
    records, _ = tail.poll(terminal=True)
    assert [r[0] for r in records] == [1, 2, 3]
    assert records[1][2] and records[2][1]["Elapsed Time [s]"] == "1"


def test_truncate_and_replace_reset(tmp_path):
    path = tmp_path / "s.csv"
    path.write_bytes(csv_bytes([row(i) for i in range(5)]))
    tail = CsvTail(path)
    tail.poll()
    path.write_bytes(csv_bytes([row(0)]))
    records, reset = tail.poll()
    assert reset and records[0][0] == 1
    other = tmp_path / "new.csv"
    other.write_bytes(csv_bytes([row(2)]))
    os.replace(other, path)
    records, reset = tail.poll()
    assert reset and records[0][1]["Elapsed Time [s]"] == "2"


def test_invalid_header_remains_error_and_recovers(tmp_path):
    path = tmp_path / "s.csv"
    path.write_text("wrong,header\n")
    tail = CsvTail(path)
    for _ in range(2):
        with pytest.raises(ValueError, match="header"):
            tail.poll()
    replacement = tmp_path / "fixed.csv"
    replacement.write_bytes(csv_bytes([row()]))
    os.replace(replacement, path)
    assert tail.poll()[0][0][0] == 1


def test_buffer_sample_time_freeze_and_capacity():
    buffer = SampleBuffer()
    for i in range(801):
        buffer.append({"elapsedMs": i * 100, "seq": i})
    assert len(buffer.samples) == 601
    assert buffer.samples[0]["elapsedMs"] == 20000
    assert buffer.latest["elapsedMs"] == 80000
    with pytest.raises(ValueError):
        buffer.append({"elapsedMs": 0})
    assert len(buffer.samples) == 601


def test_restore_60_seconds_append_and_restart(tmp_path):
    settings, manifest, path = setup_source(tmp_path, [row(i / 10) for i in range(801)])
    manager = SourceManager(settings)
    snapshot, messages = manager.tick()
    assert messages[0]["type"] == "reset"
    assert len(snapshot["history"]) == 601
    assert snapshot["history"][0]["elapsedMs"] == 20000
    first_session = snapshot["serverSessionId"]
    with path.open("ab") as out:
        out.write(csv_bytes([row(i / 10) for i in range(801, 821)], False))
    snapshot, messages = manager.tick()
    batch = next(m for m in messages if m["type"] == "samples")
    assert len(batch["samples"]) == 20
    assert batch["samples"][-1]["elapsedMs"] == 82000
    assert manager.tick()[0]["latest"]["seq"] == 821
    reboot = SourceManager(settings).tick()[0]
    assert reboot["serverSessionId"] != first_session
    assert reboot["history"][-1]["seq"] == 821
    assert len(reboot["history"]) == 601


def test_source_error_recovery_run_change_and_no_identity_mutation(tmp_path):
    settings, manifest, path = setup_source(tmp_path)
    manager = SourceManager(settings)
    manager.tick()
    manifest["csvPath"] = str(tmp_path / "other.csv")
    settings.manifest_path.write_text(json.dumps(manifest))
    snapshot, _ = manager.tick()
    assert snapshot["system"]["validity"] == "error"
    manifest["runId"] = "run-2"
    manifest["csvPath"] = str(path)
    settings.manifest_path.write_text(json.dumps(manifest))
    snapshot, messages = manager.tick()
    assert messages[0]["type"] == "reset" and snapshot["latest"]["runId"] == "run-2"


def test_stale_running_manifest_not_live_even_after_reboot(tmp_path):
    settings, _, _ = setup_source(tmp_path, status="running")
    state = SourceManager(settings).tick()[0]["system"]
    assert state["experimentStatus"] == "unknown" and state["validity"] == "stale"
    lock = FileLock(settings.manifest_path.with_suffix(".lock")).acquire()
    try:
        state = SourceManager(settings).tick()[0]["system"]
        assert state["experimentStatus"] == "running" and state["writerActive"] is True
    finally:
        lock.release()


def test_waiting_partial_final_and_invalid_manifest(tmp_path):
    settings = Settings(manifest_path=tmp_path / "missing.json", data_root=tmp_path, mock_data_root=tmp_path / "mock_runs")
    manager = SourceManager(settings)
    assert manager.tick()[0]["system"]["validity"] == "waiting"
    settings.manifest_path.write_text("[]")
    assert manager.tick()[0]["system"]["validity"] == "error"
    settings, manifest, path = setup_source(tmp_path)
    with path.open("ab") as out:
        out.write(b'"unfinished')
    snapshot, _ = SourceManager(settings).tick()
    assert snapshot["latest"]["seq"] == 1
    assert any("Incomplete final" in e["message"] for e in snapshot["events"])


def test_manifest_lock_and_lifecycle(tmp_path):
    config = load_config()
    path = tmp_path / "current.json"
    one, two = RunManifest(config, path), RunManifest(config, path)
    one.begin()
    try:
        assert is_locked(path.with_suffix(".lock"))
        with pytest.raises(RuntimeError):
            two.begin()
        one.update(status="running", csvPath=str(tmp_path / "file.csv"))
        one.finish(130, "KeyboardInterrupt")
        data = json.loads(path.read_text())
        assert data["status"] == "interrupted" and data["endedAt"]
        assert not list(tmp_path.glob("*.tmp"))
    finally:
        one.release()
    assert not is_locked(path.with_suffix(".lock"))


def test_manifest_replace_failure_is_bounded_and_preserves_previous(tmp_path):
    manifest = RunManifest(load_config(), tmp_path / "current.json")
    manifest.begin()
    original = manifest.path.read_text()
    try:
        with patch("motor_dashboard.experiment.run_manifest.os.replace", side_effect=PermissionError("busy")) as rename:
            assert manifest.update(status="running") is False
            assert rename.call_count == 3
        assert manifest.path.read_text() == original
    finally:
        manifest.release()


def test_websocket_snapshot_live_and_slow_client_reset(tmp_path):
    settings, _, path = setup_source(tmp_path)
    app = create_app(settings)
    with TestClient(app) as client:
        with client.websocket_connect("/ws/telemetry") as ws:
            message = ws.receive_json()
            assert message["type"] == "snapshot"
            while not message.get("history"):
                message = ws.receive_json()
                if message["type"] not in {"snapshot", "reset"}:
                    continue
            with path.open("ab") as out:
                out.write(csv_bytes([row(0.1)], False))
            for _ in range(30):
                message = ws.receive_json()
                if message["type"] == "samples":
                    assert message["samples"][-1]["seq"] == 2
                    break
            else:
                pytest.fail("No appended sample delivered")
        assert client.get("/api/motors").json()["motors"][0]["model"] == "XM430-W210"
        assert client.get("/api/missing").status_code == 404
        assert client.get("/assets/missing.js").status_code == 404
    hub = TelemetryHub(app.state.hub.snapshot, queue_size=2)
    slow, fast = hub.subscribe(), hub.subscribe()
    fast.get_nowait()
    hub.publish(hub.snapshot, [{"type": "system", "system": {}}])
    fast.get_nowait()
    hub.publish(hub.snapshot, [{"type": "system", "system": {}}])
    assert slow.get_nowait()["type"] == "reset"
    assert fast.get_nowait()["type"] == "system"


def test_static_routes_and_server_does_not_import_sdk(tmp_path):
    settings = Settings(manifest_path=tmp_path / "missing.json", data_root=tmp_path, mock_data_root=tmp_path / "mock_runs")
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<h1>dashboard</h1>")
    with TestClient(create_app(settings, dist)) as client:
        assert client.get("/").status_code == 200
        assert client.get("/trends").status_code == 200
        assert client.get("/api/nope").status_code == 404
    code = "import sys; from bootstrap import load_package; load_package(); from motor_dashboard.main import create_app; create_app(); assert 'dynamixel_sdk' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], cwd=PROJECT_ROOT, check=True)

def test_truncate_regrow_past_offset_detects_changed_anchor(tmp_path):
    path = tmp_path / "s.csv"
    path.write_bytes(csv_bytes([row(0), row(1)]))
    tail = CsvTail(path)
    tail.poll()
    path.write_bytes(csv_bytes([row(100), row(101), row(102)]))
    records, changed = tail.poll()
    assert changed and records[0][0] == 1
    assert records[0][1]["Elapsed Time [s]"] == "100"


def test_corrupt_utf8_remains_error_until_file_replaced(tmp_path):
    path = tmp_path / "s.csv"
    path.write_bytes(csv_bytes([row()]) + b"\xff")
    tail = CsvTail(path)
    for _ in range(2):
        with pytest.raises(ValueError, match="UTF-8"):
            tail.poll()
    replacement = tmp_path / "fixed.csv"
    replacement.write_bytes(csv_bytes([row(1)]))
    os.replace(replacement, path)
    assert tail.poll()[0][0][0] == 1


def test_old_measurement_does_not_become_fresh_by_touching_file(tmp_path):
    settings, _, path = setup_source(tmp_path, status="running")
    lock = FileLock(settings.manifest_path.with_suffix(".lock")).acquire()
    try:
        os.utime(path, None)
        state = SourceManager(settings).tick()[0]["system"]
        assert state["validity"] == "stale"
    finally:
        lock.release()


def test_delayed_header_and_final_hardware_error_are_preserved(tmp_path):
    settings, manifest, path = setup_source(tmp_path, [], status="running")
    manager = SourceManager(settings)
    assert manager.tick()[0]["latest"] is None
    with path.open("ab") as output:
        output.write(csv_bytes([row(0.1, **{"Hardware Error Status": "32"})], False))
    manifest["status"] = "failed"
    manifest["error"] = "Hardware Error Status=32"
    settings.manifest_path.write_text(json.dumps(manifest))
    snapshot, _ = manager.tick()
    assert snapshot["latest"]["hwError"] == 32
    assert snapshot["system"]["experimentStatus"] == "failed"
    assert manager.tick()[0]["latest"]["status"] == "critical"
