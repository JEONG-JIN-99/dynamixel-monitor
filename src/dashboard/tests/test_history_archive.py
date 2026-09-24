import csv
import json
import time
from dataclasses import replace
from unittest.mock import patch

from fastapi.testclient import TestClient
from motor_dashboard.main import create_app
from motor_dashboard.mock_source import MockSource
from motor_dashboard.history_archive import MockArchive
from motor_dashboard.settings import Settings
from motor_dashboard.tests.test_pipeline import setup_source, row


def test_archive_roundtrip_windows_and_uncommitted_tail(tmp_path):
    source = MockSource(started_ms=100000)
    assert source.buffer.latest["elapsedMs"] == 0
    archive = MockArchive(tmp_path / "mock_runs", source)
    rows = [source.buffer.latest] + [source.sample(t) for t in range(100, 3600100, 100)]
    archive.append(rows)
    for duration in (60, 300, 600, 1800, 3600, 0):
        result = archive.query(duration)
        expected = [s for s in rows if s["elapsedMs"] >= (3600000 - duration * 1000 if duration else 0)]
        assert result["samples"] == expected
        assert result["throughSeq"] == rows[-1]["seq"]
    assert archive.query(0, after_seq=rows[-2]["seq"])["samples"] == rows[-1:]
    assert archive.query(0, motor_id=2)["samples"] == []
    # A concurrent reader never consumes a partial, uncommitted record.
    with archive.path.open("ab") as handle:
        handle.write(b'"partial')
    assert archive.query(60)["samples"] == rows[-601:]
    archive.close()
    assert json.loads(archive.metadata_path.read_text(encoding="utf-8"))["status"] == "completed"


def test_history_endpoint_matches_live_samples_and_validates_identity(tmp_path):
    settings = Settings(manifest_path=tmp_path / "absent.json", mock_data_root=tmp_path / "mock_runs")
    app = create_app(settings, mock_prehistory_ms=125000)
    with TestClient(app) as client:
        with client.websocket_connect("/ws/telemetry?source=mock") as ws:
            snap = ws.receive_json()
            params = dict(source="mock", runId=snap["runId"], sourceSessionId=snap["sourceSessionId"], durationSec=0)
            full = client.get("/api/history", params=params).json()
            assert full["samples"][0]["elapsedMs"] == 0
            assert len(full["samples"]) > len(snap["history"])
            indexed = {s["seq"]: s for s in full["samples"]}
            assert all(indexed[s["seq"]] == s for s in snap["history"])
            live = ws.receive_json()["samples"][0]
            after = client.get("/api/history", params=params).json()
            assert next(s for s in after["samples"] if s["seq"] == live["seq"]) == live
            recent = client.get("/api/history", params={**params, "durationSec":60}).json()
            assert recent["latestElapsedMs"] - recent["samples"][0]["elapsedMs"] <= 60000
            assert client.get("/api/history", params={**params, "runId":"../outside"}).status_code == 409
            assert client.get("/api/history", params={**params, "durationSec":42}).status_code == 422
            assert client.get("/api/history", params={**params, "source":"invalid"}).status_code == 422
        before = app.state.mock_archive.seq
        deadline = time.monotonic() + 2
        while app.state.mock_archive.seq <= before and time.monotonic() < deadline:
            time.sleep(.02)
        assert app.state.mock_archive.seq > before  # recording continues without viewers
    assert app.state.mock_archive.handle.closed
    first_path = app.state.mock_archive.path
    with TestClient(create_app(settings, mock_prehistory_ms=0)) as second:
        with second.websocket_connect("/ws/telemetry?source=mock") as ws:
            assert ws.receive_json()["runId"] != snap["runId"]
    assert first_path.exists()
    assert len(list(settings.mock_data_root.rglob("telemetry.csv"))) == 2


def test_real_csv_history_reads_original_without_writing_experiment(tmp_path):
    settings, manifest, path = setup_source(tmp_path, [row(i / 10) for i in range(1301)])
    before = path.read_bytes()
    with TestClient(create_app(settings)) as client:
        with client.websocket_connect("/ws/telemetry") as ws:
            snap = ws.receive_json()
            while not snap.get("latest"):
                snap = ws.receive_json()
            params = dict(source="csv", runId=snap["runId"], sourceSessionId=snap["sourceSessionId"], durationSec=0)
            full = client.get("/api/history", params=params)
            assert full.status_code == 200
            data = full.json()
            assert data["samples"][0]["elapsedMs"] == 0
            assert len(data["samples"]) > 601
            assert path.read_bytes() == before


def test_archive_failure_stops_broadcasting_new_measurements(tmp_path):
    app = create_app(Settings(manifest_path=tmp_path / "absent", mock_data_root=tmp_path / "mock"), mock_prehistory_ms=0)
    with TestClient(app) as client:
        with patch.object(app.state.mock_archive, "append", side_effect=OSError("disk full")):
            deadline = time.monotonic() + 2
            while not app.state.archive_error and time.monotonic() < deadline:
                time.sleep(.02)
            assert app.state.archive_error == "disk full"
            with client.websocket_connect("/ws/telemetry?source=mock") as ws:
                snapshot = ws.receive_json()
                assert snapshot["system"]["validity"] == "error"
                assert snapshot["latest"]["seq"] == app.state.mock_archive.seq
                params = dict(source="mock", runId=snapshot["runId"], sourceSessionId=snapshot["sourceSessionId"])
                assert client.get("/api/history", params=params).status_code == 503
