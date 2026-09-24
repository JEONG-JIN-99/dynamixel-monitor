"""Append-only mock CSV archive. No real experiment paths or motor access."""
import csv
import json
import threading
from datetime import datetime, timezone
from pathlib import Path


class MockArchive:
    fields = ["serverSessionId", "sourceSessionId", "runId", "busId", "seq", "id", "model",
              "elapsedMs", "timestamp", "receivedAt", "basePosition", "registers", "diagnosis"]

    def __init__(self, root, source, directory=None):
        self.source = source
        self.directory = Path(directory) if directory else Path(root) / source.run_id
        if directory is None:
            self.directory.mkdir(parents=True, exist_ok=False)
        self.path = self.directory / "telemetry.csv"
        self.metadata_path = self.directory / "metadata.json"
        self.lock = threading.Lock()
        self.handle = self.path.open("x", encoding="utf-8", newline="")
        self.writer = csv.DictWriter(self.handle, fieldnames=self.fields)
        self.writer.writeheader()
        self.handle.flush()
        self.offset = self.path.stat().st_size
        self.seq = 0
        self.elapsed_ms = 0
        self.metadata = {"schemaVersion": 1, "simulated": True, "runId": source.run_id,
                         "startedAt": source.snapshot()["experiment"]["startedAt"],
                         "endedAt": None, "status": "running", "sampleIntervalSec": source.interval_sec,
                         "motorModel": "XM430-W210", "motorId": 1}
        self.managed = directory is not None
        if not self.managed:
            self.save_metadata()

    def save_metadata(self):
        temporary = self.metadata_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.metadata_path)

    def append(self, samples):
        with self.lock:
            for sample in samples:
                if sample["seq"] <= self.seq:
                    raise ValueError("Archive sequence must increase")
                row = {k: sample.get(k) for k in self.fields}
                for key in ("registers", "diagnosis"):
                    row[key] = json.dumps(row[key], ensure_ascii=False, separators=(",", ":"))
                self.writer.writerow(row)
                # Publish only after the complete record is visible to readers.
                self.handle.flush()
                self.offset = self.path.stat().st_size
                self.seq = sample["seq"]
                self.elapsed_ms = sample["elapsedMs"]

    def query(self, duration_sec=0, after_seq=0, motor_id=None, model=None):
        with self.lock:
            end_offset, through, elapsed = self.offset, self.seq, self.elapsed_ms
        cutoff = max(0, elapsed - duration_sec * 1000) if duration_sec else 0
        samples = []
        # JSON strings escape newlines, so each archive record occupies one physical line.
        with self.path.open("rb") as handle:
            header = next(csv.reader([handle.readline().decode("utf-8")]))
            while handle.tell() < end_offset:
                line = handle.readline()
                if not line or handle.tell() > end_offset:
                    break
                row = dict(zip(header, next(csv.reader([line.decode("utf-8")]))))
                seq, timestamp = int(row["seq"]), int(row["elapsedMs"])
                if seq <= after_seq or timestamp < cutoff:
                    continue
                if motor_id is not None and int(row["id"]) != motor_id or model and row["model"] != model:
                    continue
                for key in ("seq", "id", "elapsedMs", "timestamp", "receivedAt"):
                    row[key] = int(row[key])
                if "basePosition" in row:
                    row["basePosition"] = float(row["basePosition"]) if row["basePosition"] else None
                for key in ("registers", "diagnosis"):
                    row[key] = json.loads(row[key])
                samples.append(row)
        return {"schemaVersion": 1, "runId": self.source.run_id,
                "serverSessionId": self.source.server_session_id,
                "sourceSessionId": self.source.source_session_id,
                "throughSeq": through, "latestElapsedMs": elapsed, "samples": samples}

    def close(self, error=None):
        with self.lock:
            if self.handle.closed:
                return
            self.handle.close()
            self.metadata.update(status="failed" if error else "completed", error=error,
                                 endedAt=datetime.now(timezone.utc).isoformat())
            if not self.managed:
                self.save_metadata()
