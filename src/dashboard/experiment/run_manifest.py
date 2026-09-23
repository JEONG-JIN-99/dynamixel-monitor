"""The copied experiment publishes its CSV selection, never telemetry."""
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import time
from uuid import uuid4

if __package__ and "." in __package__:
    from ..file_lock import FileLock
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from file_lock import FileLock

DEFAULT_MANIFEST = Path(__file__).resolve().parents[1] / "runtime" / "current_experiment.json"


class RunManifest:
    def __init__(self, config, path=DEFAULT_MANIFEST):
        self.path = Path(path)
        self.lock = FileLock(self.path.with_suffix(".lock"))
        self.active = False
        self.data = {
            "schemaVersion": 1, "runId": str(uuid4()), "status": "preparing",
            "csvPath": None, "metadataPath": None,
            "motorModel": config.motor_name, "motorId": config.motor_id,
            "startedAt": datetime.now().astimezone().isoformat(),
            "updatedAt": None, "endedAt": None,
            "sampleIntervalSec": config.sample_interval_sec,
            "flushEveryRows": config.flush_every_rows, "error": None,
        }

    def begin(self):
        self.lock.acquire()
        self.active = True
        try:
            self.update(required=True)
        except Exception:
            self.release()
            raise

    def update(self, required=False, **values):
        self.data.update(values)
        self.data["updatedAt"] = datetime.now().astimezone().isoformat()
        temporary = self.path.with_name(self.path.name + "." + self.data["runId"] + ".tmp")
        for attempt in range(3):
            try:
                temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
                os.replace(temporary, self.path)
                return True
            except OSError as exc:
                if attempt == 2:
                    try:
                        temporary.unlink(missing_ok=True)
                    except OSError:
                        pass
                    if required:
                        raise
                    print(f"WARNING: Could not update dashboard manifest: {exc}")
                    return False
                time.sleep(0.02)

    def finish(self, code, error=None):
        if not self.active:
            return
        self.update(status={0: "completed", 130: "interrupted"}.get(code, "failed"),
                    endedAt=datetime.now().astimezone().isoformat(), error=error)

    def release(self):
        self.lock.release()
        self.active = False
