"""Device-free, explicitly simulated CSV writer for the complete pipeline."""
import argparse
import csv
from dataclasses import replace
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from src.dashboard.experiment.configuration import load_config
from src.dashboard.experiment.run_manifest import RunManifest

ROOT = Path(__file__).resolve().parents[1] / "runtime" / "demo"


def main():
    parser = argparse.ArgumentParser(description="Write simulated data only to dashboard/runtime/demo")
    parser.add_argument("--duration", type=float, default=120, help="Live duration in seconds")
    parser.add_argument("--seed-seconds", type=float, default=60, help="Initial simulated history, 0..3600")
    args = parser.parse_args()
    if not 0 < args.duration <= 86400 or not 0 <= args.seed_seconds <= 3600:
        parser.error("duration: 0..86400; seed-seconds: 0..3600")
    config = replace(load_config(), motor_name="XM430-W210", motor_id=1,
                     sample_interval_sec=0.1, flush_every_rows=10)
    manifest = RunManifest(config, ROOT / "current_experiment.json")
    code, error = 0, None
    try:
        manifest.begin()
        path = ROOT / f"SIMULATED_{manifest.data['runId']}.csv"
        meta_path = path.with_suffix(".json")
        start_time = datetime.now().astimezone() - timedelta(seconds=args.seed_seconds)
        meta_path.write_text(json.dumps({
            "schema_version": 4, "experiment": "simulated-cycle", "simulated": True,
            "condition": "SIMULATED", "created_at": start_time.isoformat(),
            "settings": config.snapshot(), "model_number": 1030, "firmware_version": None,
        }, indent=2), encoding="utf-8")

        def row(t):
            phase = t % 14
            up = phase < 7
            local = min(phase % 7, 6)
            position = round(100 + 4096 * (1 - math.cos(local / 6 * math.pi)) / 2 * (1 if up else -1) + (0 if up else 4096))
            current = round(100 + 65 * math.sin(t * 0.9))
            return {
                "PC Time": (start_time + timedelta(seconds=t)).replace(tzinfo=None).isoformat(timespec="milliseconds"),
                "Elapsed Time [s]": f"{t:.6f}", "Motor Model": "XM430-W210", "Motor ID": 1,
                "Experiment": "simulated-cycle", "Condition": "SIMULATED", "Load [kg]": "",
                "Cycle": int(t / 14) + 1, "Phase": "UP" if up else "DOWN",
                "Target Turns": 1, "Base Position": 100, "Goal Position": 4196 if up else 100,
                "Profile Acceleration": 2000, "Profile Velocity": 6000,
                "Hardware Error Status": 0, "Realtime Tick": round(t * 1000) % 32768,
                "Moving": int(phase % 7 < 6), "Moving Status": 2 if phase % 7 < 6 else 1,
                "Present PWM": round(120 * math.sin(t)), "Present Current": current,
                "Present Velocity": round(35 * math.sin(local / 6 * math.pi) * (1 if up else -1)),
                "Present Position": position, "Velocity Trajectory": round(35 * math.sin(t)),
                "Position Trajectory": position + round(8 * math.sin(t * 2)),
                "Present Input Voltage": 120, "Present Temperature": 32,
                "Present Current [mA]": round(current * 2.69, 6),
            }

        with path.open("x", encoding="utf-8-sig", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=list(row(0)))
            writer.writeheader()
            count = round(args.seed_seconds * 10)
            for index in range(count):
                writer.writerow(row(index / 10))
            output.flush()
            manifest.update(status="running", csvPath=str(path.resolve()), metadataPath=str(meta_path.resolve()))
            print(f"SIMULATED CSV: {path}", flush=True)
            started = time.monotonic()
            while time.monotonic() - started < args.duration:
                writer.writerow(row(count / 10))
                count += 1
                if count % config.flush_every_rows == 0:
                    output.flush()
                time.sleep(max(0, started + (count - round(args.seed_seconds * 10)) / 10 - time.monotonic()))
    except KeyboardInterrupt:
        code, error = 130, "KeyboardInterrupt"
    except Exception as exc:
        code, error = 1, str(exc)
        print(error)
    finally:
        try:
            manifest.finish(code, error)
        finally:
            manifest.release()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
