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

    def __init__(self, server_session_id=None, started_ms=None, prehistory_ms=0, config=None, run_id=None):
        self.config = config
        self.finished = False
        self.status = "running"
        if config:
            self.interval_sec = config.sample_interval_sec
        self.server_session_id = server_session_id or str(uuid4())
        self.run_id = run_id or "mock-" + str(uuid4())
        self.source_session_id = self.run_id + ":1"
        self.started_ms = started_ms if started_ms is not None else round(time.time() * 1000) - prehistory_ms
        self.buffer = SampleBuffer(60, math.ceil(60 / self.interval_sec) + 1)
        self.seq = 0
        # Production runs begin at zero; prehistory is reserved for isolated fixtures.
        for elapsed_ms in range(0, prehistory_ms + 1, max(1, round(self.interval_sec * 1000))):
            self.buffer.append(self.sample(elapsed_ms))

    @property
    def cycle_seconds(self):
        return (2*self.config.profile_duration_ms/1000 + self.config.top_dwell_sec + self.config.bottom_dwell_sec) if self.config else 14

    def sample(self, elapsed_ms):
        self.seq += 1
        t = elapsed_ms / 1000
        phase = t % 14
        up = phase < 7
        progress = min(phase % 7, 6) / 6
        moving = phase % 7 < 6
        trajectory = round(100 + 2048 * (1 - math.cos(progress * math.pi)) * (1 if up else -1) + (0 if up else 4096))
        velocity_trajectory = (1 if up else -1) * 5 * math.pi / 2 * math.sin(progress * math.pi) if moving else 0
        if self.config:
            c = self.config
            move = c.profile_duration_ms / 1000
            accel = c.acceleration_ms / 1000
            phase = t % self.cycle_seconds
            up = phase < move + c.top_dwell_sec
            local = phase if up else phase - move - c.top_dwell_sec
            local = min(local, move)
            moving = local < move and not self.finished
            peak = 1 / (move - accel)
            if local < accel:
                progress, speed = peak * local * local / (2 * accel), peak * local / accel
            elif local < move - accel:
                progress, speed = peak * (local - accel / 2), peak
            else:
                progress, speed = 1 - peak * (move-local)**2 / (2*accel), peak * (move-local) / accel
            trajectory = round(100 + c.travel_pulses * (progress if up else 1-progress))
            velocity_trajectory = c.travel_pulses / 4096 * 60 * speed * (1 if up else -1) if moving else 0
            if self.finished:
                trajectory, velocity_trajectory, up = 100, 0, False
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
        if self.config:
            c = self.config
            raw.update({0:c.model.number, 7:c.motor_id, 8:{9600:0,57600:1,115200:2,1000000:3,2000000:4,3000000:5,4000000:6,4500000:7}[c.baudrate], 10:4, 108:c.acceleration_ms,
                        112:c.profile_duration_ms, 116:100+c.travel_pulses if up else 100})
        timestamp = self.started_ms + elapsed_ms
        return {
            "serverSessionId": self.server_session_id, "sourceSessionId": self.source_session_id,
            "runId": self.run_id, "busId": "mock", "seq": self.seq,
            "id": self.config.motor_id if self.config else 1, "model": self.config.motor_name if self.config else "XM430-W210", "elapsedMs": elapsed_ms,
            "timestamp": timestamp, "receivedAt": timestamp, "basePosition": 100,
            "registers": {str(a): {"raw": v, "receivedAt": timestamp, "status": "received"} for a, v in raw.items()},
            "diagnosis": {"state": "fault" if scenario else "normal", "codes": [scenario] if scenario else []},
        }

    def snapshot(self):
        latest = self.buffer.latest
        return {
            "serverSessionId": self.server_session_id, "sourceSessionId": self.source_session_id,
            "runId": self.run_id, "latest": latest, "history": list(self.buffer.samples),
            "retentionSec": 60, "capacity": math.ceil(60/self.interval_sec)+1, "seq": self.seq,
            "experiment": {
                "runId": self.run_id, "status": self.status, "csvPath": None, "metadataPath": None,
                "motorModel": self.config.motor_name if self.config else "XM430-W210", "motorId": self.config.motor_id if self.config else 1, "sampleIntervalSec": self.interval_sec,
                "flushEveryRows": 1, "startedAt": iso(self.started_ms), "endedAt": None, "error": None,
            },
            "metadata": [{
                "id": self.config.motor_id if self.config else 1, "model": self.config.motor_name if self.config else "XM430-W210", "modelNumber": self.config.model.number if self.config else 1030, "firmware": 45,
                "simulated": True, "source": "backend-mock", "settings": self.config.snapshot() if self.config else {},
                "registers": {a: r for a, r in latest["registers"].items() if int(a) < 64},
                "limits": {"current": None, "temperature": None, "voltageMin": None, "voltageMax": None},
            }],
            "events": [{"id": self.run_id, "time": iso(self.started_ms), "severity": "info",
                        "message": "백엔드 가상 데이터 · 진단 결과는 시나리오 예시입니다."}],
            "system": {
                "sourceMode": "mock", "validity": "valid", "experimentStatus": self.status,
                "dataAgeSec": 0, "configuredHz": 1/self.interval_sec, "observedHz": 1/self.interval_sec, "expectedFlushSec": None,
                "error": None, "readerCaughtUp": True, "writerActive": self.status in {"running", "finishing"},
            },
        }

    def advance(self, elapsed_ms):
        if elapsed_ms <= self.buffer.latest["elapsedMs"]:
            return self.snapshot(), []
        sample = self.sample(elapsed_ms)
        self.buffer.append(sample)
        return self.snapshot(), [{"type": "samples", "samples": [sample]}]
