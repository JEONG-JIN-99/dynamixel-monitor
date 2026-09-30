"""U2D2를 통한 단일 모터 제어와 CSV 수집 공통 구현."""

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import threading
import time

from motor_dashboard.adapters.dynamixel.device import DynamixelDevice
from motor_dashboard.experiment.configuration import DEFAULT_CONFIG, load_config
from motor_dashboard.experiment.run_manifest import RunManifest


class Experiment(DynamixelDevice):
    def __init__(self, config, config_path=DEFAULT_CONFIG, *, run_directory=None, run_id=None, manifest_path=None):
        self.run_directory = Path(run_directory) if run_directory else None
        self.run_id = run_id
        self.manifest_path = manifest_path
        self.completed_cycles = 0
        self.config = config.validate()
        self.config_path = Path(config_path).resolve()
        self.initialize_device(config)
        self.normal_exit = False
        self.finish_event = threading.Event()
        self.base_position = None
        self.model_number = None
        self.firmware = None
        self.csv_path = None
        self.rows_since_flush = 0
        self.csv_fields = [
            "PC Time", "Elapsed Time [s]", "Motor Model", "Motor ID", "Experiment",
            "Condition", "Load [kg]",
            "Cycle", "Phase", "Target Turns", "Base Position", "Goal Position",
            "Profile Acceleration", "Profile Velocity",
        ] + [field[0] for field in self.fields] + [config.model.converted_name]

    def setup_motion(self):
        self.write(1, 64, 0)
        # Normal direction, Time-based Profile, Extended Position Control Mode.
        if self.read(1, 10) != 4:
            self.write(1, 10, 4)
        if self.read(1, 11) != 4:
            self.write(1, 11, 4)
        self.write(4, 108, self.config.acceleration_ms)
        self.write(4, 112, self.config.profile_duration_ms)
        offset = 0
        for _, address, size, _ in self.fields:
            for byte in range(size):
                self.write(2, 168 + offset * 2, address + byte)
                offset += 1
        if not self.reader.addParam(self.config.motor_id):
            raise RuntimeError("GroupSyncRead addParam failed")
        self.reader_added = True
        self.goal(self.read(4, 132, signed=True))
        self.write(1, 64, 1)
        self.torque_enabled = True
        time.sleep(0.1)
        self.base_position = self.read(4, 132, signed=True)
        target = self.base_position + self.config.travel_pulses
        if not -1048575 <= target <= 1048575:
            raise ValueError(f"Target position out of range: {target}")
        self.goal(self.base_position)
        return target

    def phase(self, direction, elapsed):
        acceleration = self.config.acceleration_ms / 1000
        duration = self.config.profile_duration_ms / 1000
        if elapsed < acceleration:
            return f"{direction}_ACCEL"
        if elapsed < duration - acceleration:
            return f"{direction}_CONSTANT"
        if elapsed < duration:
            return f"{direction}_DECEL"
        return f"{direction}_SETTLE"

    def log_row(self, writer, log_file, started, cycle, phase, goal, snapshot):
        now = time.perf_counter()
        model = self.config.model
        row = {
            "PC Time": datetime.now().isoformat(timespec="milliseconds"),
            "Elapsed Time [s]": f"{now - started:.6f}",
            "Motor Model": self.config.motor_name, "Motor ID": self.config.motor_id,
            "Experiment": "cycle", "Cycle": cycle, "Phase": phase,
            "Condition": self.config.condition_folder,
            "Load [kg]": self.config.load_kg if self.config.condition_name == "overload" else "",
            "Target Turns": self.config.direction * self.config.turns,
            "Base Position": self.base_position, "Goal Position": goal,
            "Profile Acceleration": self.config.acceleration_ms,
            "Profile Velocity": self.config.profile_duration_ms,
            **snapshot,
            model.converted_name: round(snapshot[model.feedback_name] * model.scale, 6),
        }
        writer.writerow(row)
        self.rows_since_flush += 1
        if self.rows_since_flush >= self.config.flush_every_rows:
            log_file.flush()
            self.rows_since_flush = 0
        if snapshot["Hardware Error Status"]:
            log_file.flush()
            raise RuntimeError(f"Hardware Error Status={snapshot['Hardware Error Status']}")
        return now

    def wait_sample(self, next_sample):
        next_sample += self.config.sample_interval_sec
        delay = next_sample - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
            return next_sample
        return time.perf_counter()

    def move(self, writer, log_file, started, cycle, direction, goal):
        self.goal(goal)
        move_start = time.perf_counter()
        next_sample = next_print = move_start
        while True:
            snapshot = self.snapshot()
            elapsed = time.perf_counter() - move_start
            phase = self.phase(direction, elapsed)
            now = self.log_row(writer, log_file, started, cycle, phase, goal, snapshot)
            if now >= next_print:
                field = self.config.model.feedback_name
                print(f"[{phase}] Cycle={cycle} Goal={goal} Position={snapshot['Present Position']} "
                      f"{field}={snapshot[field]} (raw)")
                next_print = now + self.config.print_interval_sec
            status = snapshot["Moving Status"]
            arrived = not (status & 2) and (status & 1) and (
                abs(goal - snapshot["Present Position"]) <= self.config.position_tolerance_pulse)
            # 직전 명령의 In-Position 상태를 새 이동 완료로 오인하지 않습니다.
            if elapsed >= self.config.profile_duration_ms / 1000 and arrived:
                log_file.flush()
                return
            if elapsed > self.config.move_timeout_sec:
                raise TimeoutError(f"{direction} movement timed out after {self.config.move_timeout_sec} s")
            next_sample = self.wait_sample(next_sample)

    def dwell(self, writer, log_file, started, cycle, phase, goal, seconds):
        end = time.perf_counter() + seconds
        next_sample = time.perf_counter()
        while time.perf_counter() < end:
            self.log_row(writer, log_file, started, cycle, phase, goal, self.snapshot())
            next_sample = self.wait_sample(next_sample)
        log_file.flush()

    def wait_for_finish(self):
        while not self.finish_event.is_set():
            try:
                command = input().strip().lower()
            except EOFError:
                return
            if command in {"q", "quit", "exit"}:
                self.finish_event.set()
                print("Finish requested. The current full cycle will complete before exit.")

    def close(self):
        if self.port_open and self.torque_enabled:
            try:
                if not self.normal_exit:
                    self.goal(self.read(4, 132, signed=True))
                    print("Current-position hold requested.")
                elif self.config.torque_off_on_normal_exit:
                    self.write(1, 64, 0)
                    self.torque_enabled = False
            except Exception as exc:
                print(f"WARNING: Failed to stop/hold motor: {exc}")
            if self.torque_enabled:
                print("Torque remains ON after program exit.")
        self.finish_event.set()
        try:
            if self.reader_added:
                self.reader.clearParam()
        finally:
            if self.port_open:
                self.port.closePort()

    def run(self):
        code = 0
        error_message = None
        manifest = RunManifest(self.config, path=self.manifest_path, run_id=self.run_id) if self.run_directory else RunManifest(self.config)
        try:
            manifest.begin()
            self.connect()
            output = self.run_directory or self.config.output_dir
            output.mkdir(parents=True, exist_ok=True)
            stem = f"{self.config.motor_name}_{self.config.condition_folder}_{datetime.now():%Y%m%d_%H%M%S_%f}"
            self.csv_path = output / ("telemetry.csv" if self.run_directory else f"{stem}.csv")
            metadata_path = output / ("motor_metadata.json" if self.run_directory else f"{stem}.json")
            # 실행 당시 값을 저장하여 나중에 설정 파일을 바꿔도 실험 조건을 추적합니다.
            metadata = {
                "schema_version": 4, "experiment": "cycle",
                "condition": self.config.condition_folder,
                "created_at": datetime.now().astimezone().isoformat(),
                "config_file": str(self.config_path), "settings": self.config.snapshot(),
                "model_number": self.model_number, "firmware_version": self.firmware,
                "feedback": {"raw_column": self.config.model.feedback_name,
                             "converted_column": self.config.model.converted_name,
                             "scale": self.config.model.scale},
            }
            with metadata_path.open("x", encoding="utf-8") as meta_file:
                json.dump(metadata, meta_file, ensure_ascii=False, indent=2)
            with self.csv_path.open("x", newline="", encoding="utf-8-sig") as log_file:
                writer = csv.DictWriter(log_file, fieldnames=self.csv_fields)
                writer.writeheader()
                log_file.flush()
                manifest.update(csvPath=str(self.csv_path.resolve()),
                                metadataPath=str(metadata_path.resolve()))
                target = self.setup_motion()
                manifest.update(status="running")
                print(f"CSV: {self.csv_path}")
                print(f"Base={self.base_position}, Target={target}, Turns={self.config.turns}")
                started = time.perf_counter()
                print("Type q and Enter to finish after the current full cycle.")
                threading.Thread(target=self.wait_for_finish, daemon=True).start()
                cycle = 0
                while not self.finish_event.is_set() and not (self.run_directory and (self.run_directory / "stop.request").exists()):
                    cycle += 1
                    self.move(writer, log_file, started, cycle, "UP", target)
                    self.dwell(writer, log_file, started, cycle, "TOP_DWELL", target,
                               self.config.top_dwell_sec)
                    self.move(writer, log_file, started, cycle, "DOWN", self.base_position)
                    self.dwell(writer, log_file, started, cycle, "BOTTOM_DWELL", self.base_position,
                               self.config.bottom_dwell_sec)
                    self.completed_cycles = cycle
                    if self.finish_event.is_set() or (
                            self.config.max_cycles and cycle >= self.config.max_cycles):
                        break
                self.normal_exit = True
        except KeyboardInterrupt:
            print("Interrupted. Current-position hold will be attempted.")
            code = 130
            error_message = "KeyboardInterrupt"
        except Exception as exc:
            print(f"ERROR: {exc}")
            code = 1
            error_message = str(exc)
        finally:
            try:
                self.close()
            except Exception as exc:
                code = 1
                error_message = f"Cleanup failed: {exc}"
                print(error_message)
            finally:
                try:
                    manifest.finish(code, error_message)
                finally:
                    manifest.release()
            if self.csv_path and self.csv_path.exists():
                print(f"Log saved (may be partial on error): {self.csv_path}")
        return code


def main(argv=None):
    parser = argparse.ArgumentParser(description="U2D2 repeated-cycle motor experiment")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Experiment TOML file")
    parser.add_argument("--check-config", action="store_true", help="Validate settings without connecting to hardware")
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
    except (OSError, ValueError, TypeError) as exc:
        parser.error(str(exc))
    print(f"Config: {args.config.resolve()}")
    print(f"Motor: {config.motor_name}, Port: {config.port}, Baud: {config.baudrate}, ID: {config.motor_id}")
    print(f"Condition: {config.condition_folder}")
    print(f"Output: {config.output_dir}")
    if args.check_config:
        print("Configuration OK. No motor connection was opened.")
        return 0
    return Experiment(config, args.config).run()
