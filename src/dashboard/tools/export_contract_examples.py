"""Export deterministic wire examples from the reference backend; no device or server."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import load_package
load_package()
from motor_dashboard.mock_source import MockSource
from motor_dashboard.experiment.configuration import load_config
from motor_dashboard.stream import TelemetryHub


def examples():
    source = MockSource(server_session_id="example-server", started_ms=1790000000000, run_id="example-run")
    snap = source.snapshot()
    hub = TelemetryHub(snap)
    sample = source.sample(100)
    source.buffer.append(sample)
    return {
        "snapshot": hub.envelope({"type": "snapshot", **snap}),
        "samples": hub.envelope({"type": "samples", "samples": [sample]}),
        "system": hub.envelope({"type": "system", "system": snap["system"], "experiment": snap["experiment"], "metadata": snap["metadata"]}),
        "reset": hub.envelope({"type": "reset", **source.snapshot()}),
        "history": {"schemaVersion": 1, "serverSessionId": source.server_session_id, "sourceSessionId": source.source_session_id, "runId": source.run_id, "throughSeq": sample["seq"], "latestElapsedMs": sample["elapsedMs"], "samples": [snap["latest"], sample]},
        "saveConfigRequest": {"source": "mock", "config": load_config().snapshot()},
        "idleControlReply": {"saved": None, "defaults": load_config().snapshot(), "run": None, "active": False, "externalActive": False},
    }

if __name__ == "__main__":
    destination = Path(__file__).resolve().parents[1] / "contracts/examples.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(examples(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(destination)
