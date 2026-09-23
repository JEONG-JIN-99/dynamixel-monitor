"""Server-side simulation: raw registers + scripted diagnosis, never motor SDK access."""
import math
import time
from datetime import datetime, timezone
from uuid import uuid4

from .buffer import SampleBuffer


def iso(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()


class MockSource:
    interval_sec = 0.1

    def __init__(self, server_session_id=None, started_ms=None):
        self.server_session_id = server_session_id or str(uuid4())
        self.run_id = "mock-" + str(uuid4())
        self.source_session_id = self.run_id + ":1"
        self.started_ms = started_ms if started_ms is not None else round(time.time() * 1000) - 60000
        self.buffer = SampleBuffer(60, 601)
        self.seq = 0
        # Explicitly simulated prehistory so the example can be inspected immediately.
        for elapsed_ms in range(0, 60001, 100):
            self.buffer.append(self.sample(elapsed_ms))

    def sample(self, elapsed_ms):
        self.seq += 1
        t = elapsed_ms / 1000
        phase = t % 14
        up = phase < 7
        progress = min(phase % 7, 6) / 6
        moving = phase % 7 < 6
        trajectory = round(100 + 2048 * (1 - math.cos(progress * math.pi)) * (1 if up else -1) + (0 if up else 4096))
        velocity_trajectory = (1 if up else -1) * 5 * math.pi / 2 * math.sin(progress * math.pi) if moving else 0
        # Scripted UI examples, not an actual diagnostic algorithm or physical fault model.
        scenario = "friction" if 20 <= t % 30 < 25 else "overload" if t % 30 >= 25 else None
        current = .29 + .19 * math.sin(t * .9) + .03 * math.sin(t * 8) + (.4 if scenario else 0)
        error = round((70 if scenario else 8) * math.sin(t * 2))
        velocity = velocity_trajectory + (.9 if scenario else .18) * math.sin(t * 2) if moving else 0
        raw = {
            0: 1030, 2: 0, 6: 45, 7: 1, 8: 1, 9: 250, 10: 0, 11: 4, 12: 255, 13: 2,
            20: 0, 24: 10, 31: 80, 32: 160, 34: 95, 36: 885, 38: 1193,
            44: 330, 48: 4095, 52: 0, 60: 0, 63: 52,
            64: 1, 65: 0, 68: 2, 69: 0, 70: 0, 76: 1920, 78: 100,
            80: 0, 82: 0, 84: 800, 88: 0, 90: 0, 98: 0,
            100: 0, 102: 0, 104: 0, 108: 10, 112: 65,
            116: 4196 if up else 100, 120: elapsed_ms % 32768,
            122: int(moving), 123: 2 if moving else 1,
            124: round(12 * math.sin(t * .8) / .113),
            126: round(current / .00269), 128: round(velocity / .229),
            132: trajectory + error, 136: round(velocity_trajectory / .229), 140: trajectory,
            144: round((12 + .06 * math.sin(t * .5)) * 10),
            146: 32 + round(2 * (1 + math.sin(t / 60))), 147: 0,
        }
        timestamp = self.started_ms + elapsed_ms
        return {
            "serverSessionId": self.server_session_id, "sourceSessionId": self.source_session_id,
            "runId": self.run_id, "busId": "mock", "seq": self.seq,
            "id": 1, "model": "XM430-W210", "elapsedMs": elapsed_ms,
            "timestamp": timestamp, "receivedAt": timestamp,
            "registers": {str(a): {"raw": v, "receivedAt": timestamp, "status": "received"} for a, v in raw.items()},
            "diagnosis": {"state": "fault" if scenario else "normal", "codes": [scenario] if scenario else []},
        }

    def snapshot(self):
        latest = self.buffer.latest
        return {
            "serverSessionId": self.server_session_id, "sourceSessionId": self.source_session_id,
            "runId": self.run_id, "latest": latest, "history": list(self.buffer.samples),
            "retentionSec": 60, "capacity": 601, "seq": self.seq,
            "experiment": {
                "runId": self.run_id, "status": "running", "csvPath": None, "metadataPath": None,
                "motorModel": "XM430-W210", "motorId": 1, "sampleIntervalSec": self.interval_sec,
                "flushEveryRows": 1, "startedAt": iso(self.started_ms), "endedAt": None, "error": None,
            },
            "metadata": [{
                "id": 1, "model": "XM430-W210", "modelNumber": 1030, "firmware": 45,
                "simulated": True, "source": "backend-mock", "settings": {},
                "registers": {a: r for a, r in latest["registers"].items() if int(a) < 64},
                "limits": {"current": None, "temperature": None, "voltageMin": None, "voltageMax": None},
            }],
            "events": [{"id": self.run_id, "time": iso(self.started_ms), "severity": "info",
                        "message": "백엔드 가상 데이터 · 초기 60초 합성 이력 · 진단 결과는 시나리오 예시입니다."}],
            "system": {
                "sourceMode": "mock", "validity": "valid", "experimentStatus": "running",
                "dataAgeSec": 0, "configuredHz": 10, "observedHz": 10, "expectedFlushSec": None,
                "error": None, "readerCaughtUp": True, "writerActive": True,
            },
        }

    def advance(self, elapsed_ms):
        if elapsed_ms <= self.buffer.latest["elapsedMs"]:
            return self.snapshot(), []
        sample = self.sample(elapsed_ms)
        self.buffer.append(sample)
        return self.snapshot(), [{"type": "samples", "samples": [sample]}]
