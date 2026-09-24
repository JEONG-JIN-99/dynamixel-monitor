"""File work runs in one worker thread; no motor or SDK imports."""
import json
from pathlib import Path
import time
from uuid import uuid4

from .alerts import Events
from .buffer import SampleBuffer
from .csv_reader import CsvTail
from .file_lock import is_locked
from .normalize import normalize

TERMINAL = {"completed", "interrupted", "failed"}


class SourceManager:
    def __init__(self, settings):
        self.settings = settings
        self.server_session = str(uuid4())
        self.manifest = None
        self.metadata = {}
        self.reader = None
        self.identity = None
        self.source_session = None
        self.buffer = SampleBuffer(settings.retention_sec, settings.max_samples)
        self.events = Events()
        self.system = {"sourceMode": "csv", "validity": "waiting", "experimentStatus": "unknown",
                       "dataAgeSec": None, "configuredHz": None, "observedHz": None,
                       "expectedFlushSec": None, "error": None, "readerCaughtUp": True}
        self.messages = []
        self.reset_pending = False

    def event(self, key, value, message, severity="info"):
        event = self.events.change(key, value, message, severity)
        if event:
            self.messages.append({"type": "event", "event": event})

    def validate_manifest(self, value):
        if not isinstance(value, dict):
            raise ValueError("Manifest must be a JSON object")
        if value.get("schemaVersion") != 1 or not isinstance(value.get("runId"), str) or not value["runId"]:
            raise ValueError("Invalid manifest schema or runId")
        if value.get("status") not in TERMINAL | {"preparing", "running"}:
            raise ValueError("Invalid experiment status")
        if value.get("motorModel") not in {"XM430-W210", "XM430-W350", "XL430-W250"}:
            raise ValueError("Unsupported manifest motor model")
        if type(value.get("motorId")) is not int or not 0 <= value["motorId"] <= 252:
            raise ValueError("Invalid motor ID")
        interval, flush = value.get("sampleIntervalSec"), value.get("flushEveryRows")
        if not isinstance(interval, (int, float)) or not 0 < interval <= 60:
            raise ValueError("Invalid sample interval")
        if type(flush) is not int or not 1 <= flush <= 100000:
            raise ValueError("Invalid flush count")
        for key in ("csvPath", "metadataPath"):
            if value.get(key):
                path = Path(value[key])
                if not path.is_absolute() or not any(path.resolve().is_relative_to(root.resolve()) for root in (self.settings.data_root, self.settings.experiment_data_root)):
                    raise ValueError(f"{key} must be inside configured data_root")
        return value

    def select(self, manifest):
        new_run = self.manifest is None or self.manifest["runId"] != manifest["runId"]
        identity = (manifest["csvPath"], manifest["metadataPath"], manifest["motorModel"], manifest["motorId"])
        if not new_run and (self.manifest["motorModel"], self.manifest["motorId"]) != (manifest["motorModel"], manifest["motorId"]):
            raise ValueError("The same runId changed motor identity")
        if not new_run and self.identity is not None and self.identity != identity:
            raise ValueError("The same runId changed CSV path or motor identity")
        if new_run:
            self.reader = None
            self.identity = None
            self.metadata = {}
            self.buffer.clear()
            self.source_session = manifest["runId"] + ":pending"
            self.events = Events()
            self.messages.clear()
            self.reset_pending = True
            self.event("run", manifest["runId"], f"Experiment selected: {manifest['runId']}")
        self.manifest = manifest
        if manifest.get("csvPath") and self.reader is None:
            self.identity = identity
            self.reader = CsvTail(manifest["csvPath"])
            self.source_session = manifest["runId"] + ":1"
            self.reset_pending = True
        self.event("status", manifest["status"], f"Experiment: {manifest['status']}",
                   "error" if manifest["status"] == "failed" else "info")
        if manifest.get("error"):
            self.event("experiment_error", manifest["error"], manifest["error"], "error")

    def read_rows(self):
        if self.reader is None:
            return
        if not self.metadata and self.manifest.get("metadataPath"):
            if Path(self.manifest["metadataPath"]).stat().st_size > 4 * 1024 * 1024:
                raise ValueError("Metadata exceeds 4 MiB")
            with Path(self.manifest["metadataPath"]).open(encoding="utf-8-sig") as handle:
                self.metadata = json.load(handle)
            if not isinstance(self.metadata, dict) or not isinstance(self.metadata.get("settings", {}), dict):
                self.metadata = {}
                raise ValueError("Metadata and its settings must be JSON objects")
        records, replaced = self.reader.poll(self.manifest["status"] in TERMINAL)
        if replaced:
            self.buffer.clear()
            self.source_session = self.manifest["runId"] + ":" + str(self.reader.generation)
            self.reset_pending = True
            self.event("generation", self.reader.generation, "CSV replaced or truncated; history reset", "warning")
        batch = []
        for seq, row, error in records:
            try:
                if error:
                    raise ValueError(error)
                sample = normalize(row, self.manifest, self.metadata, seq,
                                   self.server_session, self.source_session)
                previous = self.buffer.latest
                if previous:
                    gap = sample["elapsedMs"] - previous["elapsedMs"]
                    if gap > self.manifest["sampleIntervalSec"] * 3000:
                        self.event("gap", seq, f"CSV sampling gap: {gap / 1000:.2f} s (record {seq})", "warning")
                overflow = self.buffer.append(sample)
                if overflow:
                    self.event("capacity", True, "Sample capacity reached; displayed window is shorter than 60 s", "warning")
                batch.append(sample)
                self.event("hw", sample["hwError"],
                           f"Hardware Error Status: {sample['hwError']}",
                           "error" if sample["hwError"] else "info")
            except (ValueError, KeyError, TypeError) as exc:
                self.event("row_error", seq, f"CSV record {seq}: {exc}", "warning")
        if batch:
            self.messages.append({"type": "samples", "samples": batch})
        if self.reader.eof and self.manifest["status"] in TERMINAL and self.reader.record:
            self.event("partial_final", True, "Incomplete final CSV record was not displayed", "warning")

    def tick(self):
        self.messages = []
        self.reset_pending = False
        error = None
        missing = False
        try:
            if self.settings.manifest_path.stat().st_size > 65536:
                raise ValueError("Manifest exceeds 64 KiB")
            with self.settings.manifest_path.open(encoding="utf-8-sig") as handle:
                manifest = self.validate_manifest(json.load(handle))
            # Drain a bounded final chunk before switching; clients then receive an explicit reset.
            if self.manifest and self.manifest["runId"] != manifest["runId"] and self.reader:
                try:
                    self.read_rows()
                except (OSError, ValueError):
                    pass
            self.select(manifest)
            self.read_rows()
        except FileNotFoundError as exc:
            missing = True
            error = "Waiting for experiment files" if self.manifest else None
        except (OSError, ValueError, KeyError, TypeError, UnicodeError) as exc:
            error = str(exc)
            self.event("read_error", error, f"Source error: {error}", "error")
        manifest = self.manifest or {}
        latest = self.buffer.latest
        age = max(0, time.time() - self.reader.mtime) if self.reader and self.reader.mtime else None
        if latest and latest["timestamp"] is not None and age is not None:
            age = max(age, max(0, time.time() - latest["timestamp"] / 1000))
        flush_sec = manifest.get("sampleIntervalSec", 0.1) * manifest.get("flushEveryRows", 20)
        status = manifest.get("status", "unknown")
        active = is_locked(self.settings.manifest_path.with_suffix(".lock")) if manifest else False
        if status in {"preparing", "running"} and active is not True:
            status = "unknown"
        if error and not missing:
            validity = "error"
        elif not latest:
            validity = "waiting"
        elif missing or status == "unknown" or status not in TERMINAL and age is not None and age > max(5, 3 * flush_sec):
            validity = "stale"
        else:
            validity = "valid"
        samples = self.buffer.samples
        span = (samples[-1]["elapsedMs"] - samples[0]["elapsedMs"]) / 1000 if len(samples) > 1 else 0
        self.system = {
            "sourceMode": "csv", "validity": validity, "experimentStatus": status,
            "declaredExperimentStatus": manifest.get("status"), "writerActive": active,
            "dataAgeSec": age, "configuredHz": 1 / manifest["sampleIntervalSec"] if manifest else None,
            "observedHz": (len(samples) - 1) / span if span else None,
            "expectedFlushSec": flush_sec if manifest else None, "error": error,
            "readerCaughtUp": self.reader.eof if self.reader else True,
            "lastMeasurementAt": latest["timestamp"] if latest else None,
            "lastReceivedAt": latest["receivedAt"] if latest else None,
        }
        self.event("validity", validity, f"CSV source: {validity}",
                   "warning" if validity in {"stale", "error"} else "info")
        snapshot = self.snapshot()
        if self.reset_pending:
            self.messages = [{"type": "reset", **snapshot}]
        else:
            self.messages.append({"type": "system", "system": self.system, "experiment": self.manifest,
                                  "metadata": self.motor_metadata()})
        return snapshot, self.messages

    def motor_metadata(self):
        if not self.manifest:
            return []
        return [{
            "id": self.manifest["motorId"], "model": self.manifest["motorModel"],
            "modelNumber": self.metadata.get("model_number"), "firmware": self.metadata.get("firmware_version"),
            "simulated": self.metadata.get("simulated", False),
            "settings": self.metadata.get("settings", {}), "source": "experiment settings JSON",
            "limits": {"current": None, "temperature": None, "voltageMin": None, "voltageMax": None},
        }]

    def snapshot(self):
        return {"serverSessionId": self.server_session, "sourceSessionId": self.source_session,
                "runId": self.manifest.get("runId") if self.manifest else None,
                "experiment": self.manifest, "metadata": self.motor_metadata(),
                "latest": self.buffer.latest, "history": list(self.buffer.samples),
                "retentionSec": self.settings.retention_sec,
                "capacity": self.settings.max_samples,
                "seq": self.reader.seq if self.reader else 0,
                "events": list(self.events.items), "system": self.system}
