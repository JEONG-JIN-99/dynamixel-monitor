import time
import pytest
from fastapi.testclient import TestClient
from fastapi import WebSocketDisconnect
from motor_dashboard.mock_source import MockSource
from motor_dashboard.main import create_app
from motor_dashboard.settings import Settings

ADDRESSES = {0,2,6,7,8,9,10,11,12,13,20,24,31,32,34,36,38,44,48,52,60,63,64,65,68,69,70,76,78,80,82,84,88,90,98,100,102,104,108,112,116,120,122,123,124,126,128,132,136,140,144,146,147}


def test_raw_only_contract_buffer_and_diagnosis_examples():
    source = MockSource("server", started_ms=100000, prehistory_ms=60000)
    snapshot = source.snapshot()
    assert len(snapshot["history"]) == 601
    assert snapshot["history"][-1]["elapsedMs"] - snapshot["history"][0]["elapsedMs"] == 60000
    for sample in snapshot["history"]:
        assert set(map(int, sample["registers"])) == ADDRESSES
        assert "position" not in sample and "current" not in sample and "positionError" not in sample
        assert {r["receivedAt"] for r in sample["registers"].values()} == {sample["timestamp"]}
    assert snapshot["history"][210]["diagnosis"] == {"state":"fault", "codes":["friction"]}
    assert snapshot["history"][260]["diagnosis"] == {"state":"fault", "codes":["overload"]}
    assert snapshot["latest"]["diagnosis"] == {"state":"normal", "codes":[]}
    after, messages = source.advance(60100)
    assert len(after["history"]) == 601
    assert after["history"][0]["elapsedMs"] == 100
    assert messages[0]["samples"][0]["seq"] == 602
    assert source.advance(60100)[1] == []
    assert MockSource().run_id != source.run_id


def test_shared_backend_stream_and_source_isolation(tmp_path):
    app = create_app(Settings(manifest_path=tmp_path/"none.json", data_root=tmp_path, mock_data_root=tmp_path/"mock_runs"), mock_prehistory_ms=0)
    with TestClient(app) as client:
        with client.websocket_connect("/ws/telemetry?source=mock") as a:
            first = a.receive_json()
            assert first["type"] == "snapshot" and first["schemaVersion"] == 1
            assert first["system"]["sourceMode"] == "mock"
            with client.websocket_connect("/ws/telemetry?source=mock") as b:
                second = b.receive_json()
                assert second["sourceSessionId"] == first["sourceSessionId"]
                assert second["runId"] == first["runId"]
                # Both clients receive the same next frame from one server-side generator.
                msg_a = a.receive_json()
                msg_b = b.receive_json()
                while msg_a["samples"][0]["seq"] < msg_b["samples"][0]["seq"]:
                    msg_a = a.receive_json()
                assert msg_a == msg_b
                assert msg_a["type"] == "samples"
                assert msg_a["samples"][0]["elapsedMs"] > first["latest"]["elapsedMs"]
            with client.websocket_connect("/ws/telemetry") as real:
                actual = real.receive_json()
                assert actual["system"]["sourceMode"] == "csv"
                assert actual["history"] == []
        deadline = time.monotonic() + 1
        while app.state.mock_hub.subscribers and time.monotonic() < deadline:
            time.sleep(.01)
        assert not app.state.mock_hub.subscribers
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws/telemetry?source=unknown"):
                pass
