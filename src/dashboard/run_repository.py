"""Dated run folders and immutable execution configuration; no SDK access."""
import csv
import json
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4
from .experiment.configuration import ExperimentConfig, load_config
from .history_query import read_experiment_history

KST = timezone(timedelta(hours=9), "Asia/Seoul")
ACTIVE = {"preparing", "running", "finishing"}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def config_toml(config):
    sections = {
        "motor": {"name":config.motor_name, "port":config.port, "baudrate":config.baudrate,
                  "id":config.motor_id, "protocol_version":config.protocol_version},
        "condition": {"name":config.condition_name, "load_kg":config.load_kg},
        "experiment": {k:getattr(config,k) for k in ("turns","direction","acceleration_ms","profile_duration_ms",
                       "top_dwell_sec","bottom_dwell_sec","max_cycles")},
        "logging": {k:getattr(config,k) for k in ("sample_interval_sec","print_interval_sec","flush_every_rows")},
        "control": {"move_timeout_sec":config.move_timeout_sec,"position_tolerance_pulse":config.position_tolerance_pulse,
                    "torque_off_on_normal_exit":False},
    }
    return "\n\n".join("["+name+"]\n"+"\n".join(f"{k} = {json.dumps(v, ensure_ascii=False)}" for k,v in values.items())
                         for name,values in sections.items()) + "\n"


class RunRepository:
    def __init__(self, settings):
        self.roots = {"mock": settings.mock_data_root, "real": settings.experiment_data_root}
        self.control_root = settings.control_root
        self.lock = threading.RLock()
        self.paths = {}
        self.scan()

    def scan(self):
        for root in self.roots.values():
            for path in root.glob("*/*/*/*/metadata.json"):
                try:
                    meta = json.loads(path.read_text(encoding="utf-8"))
                    if meta.get("schemaVersion") == 2 and meta.get("runId"):
                        self.paths[meta["runId"]] = path.parent
                except (OSError, ValueError):
                    continue

    def saved(self):
        try:
            return json.loads((self.control_root / "saved.json").read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None

    def save_config(self, source, values):
        if source not in self.roots:
            raise ValueError("실행 대상을 선택하세요")
        config = ExperimentConfig(**values).validate()
        if config.torque_off_on_normal_exit is not False:
            raise ValueError("종료 시 토크를 유지해야 합니다")
        if config.motor_name not in {"XM430-W210", "XM430-W350"}:
            raise ValueError("지원하지 않는 모터입니다")
        if not .02 <= config.sample_interval_sec <= 10:
            raise ValueError("수집 주기는 0.02~10초로 입력하세요")
        value = {"id":str(uuid4()), "source":source, "config":config.snapshot(), "savedAt":now_iso()}
        path = self.control_root / "configurations" / (value["id"] + ".toml")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(config_toml(config), encoding="utf-8")
        atomic_json(self.control_root / "saved.json", value)
        return value

    def create(self, saved, server_session):
        config = ExperimentConfig(**saved["config"]).validate()
        started = datetime.now(timezone.utc)
        local = started.astimezone(KST)
        run_id = saved["source"] + "-" + str(uuid4())
        directory = self.roots[saved["source"]] / local.strftime("%Y/%m/%d") / (local.strftime("%H%M%S") + "_" + run_id)
        directory.mkdir(parents=True, exist_ok=False)
        (directory / "config.toml").write_text(config_toml(config), encoding="utf-8")
        meta = {"schemaVersion":2, "telemetrySchemaVersion":1 if saved["source"] == "mock" else 4,
                "runId":run_id, "serverSessionId":server_session, "sourceSessionId":run_id+":1",
                "source":saved["source"], "simulated":saved["source"] == "mock", "status":"preparing",
                "startedAt":started.isoformat(), "endedAt":None, "date":local.strftime("%Y-%m-%d"),
                "timeZone":"Asia/Seoul", "motorModel":config.motor_name, "motorId":config.motor_id,
                "condition":config.condition_name, "sampleIntervalSec":config.sample_interval_sec,
                "configId":saved["id"], "config":config.snapshot(), "configFile":"config.toml", "csvFile":"telemetry.csv",
                "stopRequestedAt":None, "stopReason":None, "error":None,
                "rowCount":0, "lastSeq":0, "elapsedMs":0, "completedCycles":0, "metadata":[]}
        atomic_json(directory / "metadata.json", meta)
        self.paths[run_id] = directory
        return meta

    def directory(self, run_id):
        if run_id not in self.paths:
            self.scan()
        if run_id not in self.paths:
            raise KeyError("실험 기록을 찾을 수 없습니다")
        return self.paths[run_id]

    def get(self, run_id):
        with self.lock:
            return json.loads((self.directory(run_id) / "metadata.json").read_text(encoding="utf-8"))

    def update(self, run_id, **changes):
        with self.lock:
            meta = self.get(run_id)
            meta.update(changes)
            atomic_json(self.directory(run_id) / "metadata.json", meta)
            return meta

    def list(self, year=None, month=None, day=None, source=None, offset=0, limit=100):
        self.scan()
        values = []
        for run_id in list(self.paths):
            try:
                values.append(self.get(run_id))
            except (OSError, ValueError):
                continue
        dates = sorted({v["date"] for v in values}, reverse=True)
        values = [v for v in values if (not source or v["source"] == source)
                  and (not year or int(v["date"][:4]) == year)
                  and (not month or int(v["date"][5:7]) == month)
                  and (not day or int(v["date"][8:10]) == day)]
        values.sort(key=lambda v:v["startedAt"], reverse=True)
        return {"runs":values[offset:offset+limit], "total":len(values), "dates":dates}

    def history(self, run_id, duration=0):
        meta = self.get(run_id)
        if meta["status"] in ACTIVE or meta["status"] == "unknown":
            raise ValueError("진행 중인 실험은 상세분석에서 확인하세요")
        directory = self.directory(run_id)
        path = directory / "telemetry.csv"
        if meta["source"] == "mock":
            cutoff = max(0, meta["elapsedMs"] - duration * 1000) if duration else 0
            samples = []
            if path.exists():
                with path.open(encoding="utf-8", newline="") as handle:
                    for row in csv.DictReader(handle):
                        if int(row["elapsedMs"]) < cutoff or int(row["seq"]) > meta["lastSeq"]:
                            continue
                        for key in ("seq","id","elapsedMs","timestamp","receivedAt"):
                            row[key] = int(row[key])
                        if "basePosition" in row:
                            row["basePosition"] = float(row["basePosition"]) if row["basePosition"] else None
                        for key in ("registers","diagnosis"):
                            row[key] = json.loads(row[key])
                        samples.append(row)
            return {"schemaVersion":1, "runId":run_id,"serverSessionId":meta["serverSessionId"],
                    "sourceSessionId":meta["sourceSessionId"],"throughSeq":meta["lastSeq"],
                    "latestElapsedMs":meta["elapsedMs"],"samples":samples}
        raw_meta_path = directory / "motor_metadata.json"
        raw_meta = json.loads(raw_meta_path.read_text(encoding="utf-8")) if raw_meta_path.exists() else {}
        snapshot = {**meta, "latest":{"seq":meta["lastSeq"],"elapsedMs":meta["elapsedMs"]},
                    "experiment": {**meta, "csvPath":str(path),"motorModel":meta["motorModel"],"motorId":meta["motorId"]}}
        return read_experiment_history(snapshot, raw_meta, directory, duration, 0, None, None, None)
