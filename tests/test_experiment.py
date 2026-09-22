"""실제 장치 없이 설정, Control Table 매핑, 저장과 종료를 검증합니다."""

import contextlib
import csv
from dataclasses import replace
import io
import json
import re
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "experiment"))
import acquisition
import configuration


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def perf_counter(self):
        return self.now

    def sleep(self, seconds):
        self.now += max(seconds, 0.000001)


class FakeDevice:
    def __init__(self, model=1030):
        self.model = model
        self.writes = []
        self.registers = {6: 42, 10: 4, 11: 4, 132: 100}
        self.indirect = {}
        self.closed = False
        self.fail_snapshot = False

    def write(self, size, port, motor_id, address, value):
        self.writes.append((size, address, value))
        self.registers[address] = value
        if size == 2 and address >= 168:
            self.indirect[224 + (address - 168) // 2] = value
        if address == 116:
            self.registers[132] = value
        return 0, 0

    def packet(self):
        packet = Mock()
        packet.ping.return_value = (self.model, 0, 0)
        for size in (1, 2, 4):
            getattr(packet, f"write{size}ByteTxRx").side_effect = (
                lambda port, motor_id, address, value, size=size: self.write(size, port, motor_id, address, value))
            getattr(packet, f"read{size}ByteTxRx").side_effect = (
                lambda port, motor_id, address: (self.registers.get(address, 0), 0, 0))
        return packet

    def reader(self):
        reader = Mock()
        reader.addParam.return_value = True
        reader.isAvailable.return_value = True
        reader.txRxPacket.side_effect = lambda: -1 if self.fail_snapshot else 0
        def get_data(motor_id, address, size):
            original = self.indirect[address]
            values = {70: 0, 120: 123, 122: 0, 123: 1, 124: 5,
                      126: 65526, 128: 0, 132: self.registers[132],
                      136: 0, 140: self.registers[132], 144: 120, 146: 25}
            return values[original]
        reader.getData.side_effect = get_data
        return reader

    def port(self):
        port = Mock()
        port.openPort.return_value = True
        port.setBaudRate.return_value = True
        port.closePort.side_effect = lambda: setattr(self, "closed", True)
        return port


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        # 사용자가 실험 기본값을 바꾸어도 모의 실험의 기준 조건은 고정합니다.
        self.base = replace(configuration.load_config(), motor_name="XM430-W210", motor_id=1,
                            port="COM5", baudrate=1000000, turns=1.0, direction=1,
                            acceleration_ms=2000, profile_duration_ms=6000,
                            condition_name="normal", load_kg=0.0)

    @contextlib.contextmanager
    def simulated(self, config, device=None):
        device = device or FakeDevice(config.model.number)
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(configuration, "PROJECT_ROOT", Path(directory)))
            stack.enter_context(patch.object(acquisition, "PortHandler", return_value=device.port()))
            stack.enter_context(patch.object(acquisition, "PacketHandler", return_value=device.packet()))
            stack.enter_context(patch.object(acquisition, "GroupSyncRead", return_value=device.reader()))
            stack.enter_context(patch.object(acquisition, "time", FakeClock()))
            stack.enter_context(patch.object(acquisition.threading, "Thread"))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            yield acquisition.Experiment(config), device

    def short_config(self, name="XM430-W210", **changes):
        values = dict(motor_name=name, acceleration_ms=10, profile_duration_ms=30,
                      sample_interval_sec=0.01, top_dwell_sec=0.02, bottom_dwell_sec=0.02,
                      max_cycles=1, move_timeout_sec=1.0)
        values.update(changes)
        return replace(self.base, **values).validate()

    def test_reject_invalid_settings(self):
        for changes in ({"motor_name": "../wrong"}, {"motor_id": 254}, {"motor_id": True},
                        {"turns": float("nan")}, {"turns": 0}, {"direction": 0},
                        {"sample_interval_sec": 0}, {"acceleration_ms": 7000},
                        {"move_timeout_sec": 6}, {"torque_off_on_normal_exit": "false"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.base, **changes).validate()

    def test_config_edit_changes_model_and_connection(self):
        text = configuration.DEFAULT_CONFIG.read_text(encoding="utf-8")
        motor = '[motor]\nname = "XM430-W350"\nport = "COM9"\nid = 2\nbaudrate = 57600\nprotocol_version = 2.0\n\n'
        text = re.sub(r"(?ms)^\[motor\].*?(?=^\[|\Z)", lambda _: motor, text, count=1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "custom.toml"
            path.write_text(text, encoding="utf-8-sig")
            config = configuration.load_config(path)
            self.assertEqual((config.motor_name, config.port, config.motor_id, config.baudrate),
                             ("XM430-W350", "COM9", 2, 57600))
            path.write_text(text.replace("turns =", "truns ="), encoding="utf-8")
            with self.assertRaises(ValueError):
                configuration.load_config(path)

    def test_signed_current_and_mapping(self):
        for name in configuration.MODELS:
            with self.subTest(model=name), self.simulated(self.short_config(name)) as (run, device):
                run.connect()
                run.setup_motion()
                values = run.snapshot()
                self.assertEqual(run.data_length, 28)
                self.assertEqual(device.indirect[231], 126)
                self.assertEqual(device.indirect[232], 127)
                self.assertEqual(values[run.config.model.feedback_name], -10)
                other = "Present Load" if name.startswith("XM") else "Present Current"
                self.assertNotIn(other, values)
                run.close()

    def test_csv_paths_units_and_config_snapshot_for_all_models(self):
        for name in configuration.MODELS:
            with self.subTest(model=name), self.simulated(self.short_config(name)) as (run, device):
                self.assertEqual(run.run(), 0)
                self.assertTrue(device.closed)
                self.assertEqual(run.csv_path.parent.name, "normal")
                self.assertEqual(run.csv_path.parent.parent.name, name)
                self.assertRegex(run.csv_path.name, rf"^{name}_normal_\d{{8}}_\d{{6}}_\d{{6}}\.csv$")
                with run.csv_path.open(encoding="utf-8-sig", newline="") as csv_file:
                    rows = list(csv.DictReader(csv_file))
                self.assertGreater(len(rows), 0)
                self.assertEqual(rows[0][run.config.model.feedback_name], "-10")
                expected = -26.9 if name.startswith("XM") else -1.0
                self.assertAlmostEqual(float(rows[0][run.config.model.converted_name]), expected)
                self.assertEqual(rows[0]["Motor Model"], name)
                self.assertEqual(rows[0]["Motor ID"], "1")
                self.assertEqual(rows[0]["Condition"], "normal")
                self.assertEqual(rows[0]["Load [kg]"], "")
                self.assertEqual(rows[0]["Experiment"], "cycle")
                self.assertIn("BOTTOM_DWELL", {row["Phase"] for row in rows})
                self.assertEqual(device.registers[132], 100)
                metadata = json.loads(run.csv_path.with_suffix(".json").read_text())
                self.assertEqual(metadata["settings"], run.config.snapshot())
                self.assertEqual(metadata["model_number"], configuration.MODELS[name].number)
                self.assertEqual(metadata["condition"], "normal")
                self.assertEqual(metadata["experiment"], "cycle")

    def test_conditions_select_separate_folders(self):
        for name in configuration.CONDITIONS:
            load = 500 if name == "overload" else 0
            config = replace(self.base, condition_name=name, load_kg=load).validate()
            expected = "overload_500kg" if load else name
            with self.subTest(condition=name):
                self.assertEqual(config.output_dir,
                                 configuration.PROJECT_ROOT / "results" / "raw" / "XM430-W210" / expected)
        for amount, expected in [(0.5, "overload_0.5kg"), (1.0, "overload_1kg"),
                                 (500.0, "overload_500kg"), (750, "overload_750kg"),
                                 (12.5, "overload_12.5kg"), (0.00001, "overload_0.00001kg")]:
            with self.subTest(amount=amount):
                config = replace(self.base, condition_name="overload", load_kg=amount).validate()
                self.assertEqual(config.output_dir.name, expected)

    def test_invalid_conditions_are_rejected(self):
        for changes in ({"condition_name": "../normal"}, {"condition_name": "overload"},
                        {"load_kg": -1}, {"load_kg": float("nan")},
                        {"load_kg": True}, {"load_kg": 500}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.base, **changes).validate()

    def test_condition_config_csv_and_json(self):
        # 실제 파일을 읽는 경로부터 반복 실험의 CSV/JSON까지 확인합니다.
        text = configuration.DEFAULT_CONFIG.read_text(encoding="utf-8-sig")
        text = text.replace('name = "normal"', 'name = "overload"').replace('load_kg = 0.0', 'load_kg = 500.0')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "overload.toml"
            path.write_text(text, encoding="utf-8")
            loaded = configuration.load_config(path)
            self.assertEqual(loaded.condition_folder, "overload_500kg")
        config = self.short_config(condition_name=loaded.condition_name, load_kg=loaded.load_kg)
        with self.simulated(config) as (run, device):
            self.assertEqual(run.run(), 0)
            self.assertEqual(run.csv_path.parent.name, "overload_500kg")
            self.assertTrue(run.csv_path.name.startswith(f"{config.motor_name}_overload_500kg_"))
            with run.csv_path.open(encoding="utf-8-sig", newline="") as csv_file:
                rows = list(csv.DictReader(csv_file))
            self.assertEqual(rows[0]["Condition"], "overload_500kg")
            self.assertEqual(float(rows[0]["Load [kg]"]), 500)
            metadata = json.loads(run.csv_path.with_suffix(".json").read_text())
            self.assertEqual(metadata["condition"], "overload_500kg")
            self.assertEqual(metadata["settings"]["load_kg"], 500)

    def test_load_rejected_for_conditions_other_than_overload(self):
        for condition in configuration.CONDITIONS:
            if condition == "overload":
                continue
            with self.subTest(condition=condition), self.assertRaises(ValueError):
                self.short_config(condition_name=condition, load_kg=200)

    def test_model_mismatch_does_not_write_controls_or_logs(self):
        with self.simulated(self.short_config(), device=FakeDevice(1020)) as (run, device):
            self.assertEqual(run.run(), 1)
            self.assertEqual(device.writes, [])
            self.assertIsNone(run.csv_path)
            self.assertTrue(device.closed)

    def test_old_firmware_does_not_write_controls(self):
        device = FakeDevice()
        device.registers[6] = 41
        with self.simulated(self.short_config(), device=device) as (run, device):
            self.assertEqual(run.run(), 1)
            self.assertEqual(device.writes, [])

    def test_normal_torque_off_and_error_hold(self):
        config = self.short_config(torque_off_on_normal_exit=True)
        with self.simulated(config) as (run, device):
            self.assertEqual(run.run(), 0)
            self.assertEqual(device.writes[-1], (1, 64, 0))
        device = FakeDevice()
        device.fail_snapshot = True
        with self.simulated(config, device=device) as (run, device):
            self.assertEqual(run.run(), 1)
            self.assertEqual(device.writes[-1][1], 116)
            self.assertEqual(device.registers[64], 1)
            self.assertTrue(device.closed)

    def test_direction_and_cycle_count(self):
        with self.simulated(self.short_config(direction=-1, max_cycles=2)) as (run, device):
            self.assertEqual(run.run(), 0)
            targets = [value for _, address, value in device.writes if address == 116]
            self.assertEqual(targets.count((-3996) & 0xFFFFFFFF), 2)
            self.assertEqual(device.registers[132], 100)

    def test_check_config_never_constructs_port(self):
        with patch.object(acquisition, "PortHandler", side_effect=AssertionError("No hardware")), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(acquisition.main(["--check-config"]), 0)

    def test_q_during_each_phase_finishes_cycle_at_base(self):
        for stop_phase in ("UP_ACCEL", "TOP_DWELL", "DOWN_ACCEL", "BOTTOM_DWELL"):
            with self.subTest(phase=stop_phase), self.simulated(self.short_config(max_cycles=3)) as (run, device):
                original_log_row = run.log_row
                def log_and_request_finish(writer, log_file, started, cycle, phase, goal, snapshot):
                    now = original_log_row(writer, log_file, started, cycle, phase, goal, snapshot)
                    if phase == stop_phase and not run.finish_event.is_set():
                        with patch("builtins.input", return_value="q"):
                            run.wait_for_finish()
                    return now
                with patch.object(run, "log_row", side_effect=log_and_request_finish):
                    self.assertEqual(run.run(), 0)
                self.assertTrue(run.normal_exit)
                self.assertTrue(device.closed)
                self.assertEqual(device.registers[132], run.base_position)
                with run.csv_path.open(encoding="utf-8-sig", newline="") as csv_file:
                    rows = list(csv.DictReader(csv_file))
                self.assertEqual({row["Cycle"] for row in rows}, {"1"})
                self.assertEqual(rows[-1]["Phase"], "BOTTOM_DWELL")
                self.assertTrue(any(row["Phase"].startswith("DOWN_") for row in rows))


if __name__ == "__main__":
    unittest.main()
