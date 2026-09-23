"""실험 설정 읽기. 장치 연결 전에 오타와 잘못된 값을 검사합니다."""

from dataclasses import asdict, dataclass
from decimal import Decimal
import math
from pathlib import Path
import tomllib

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "experiment.toml"


@dataclass(frozen=True)
class MotorModel:
    number: int
    feedback_name: str
    converted_name: str
    scale: float


# ROBOTIS 공식 Control Table: 주소 126, signed 2-byte.
# https://emanual.robotis.com/docs/en/dxl/x/xm430-w210/
# https://emanual.robotis.com/docs/en/dxl/x/xm430-w350/
# https://emanual.robotis.com/docs/en/dxl/x/xl430-w250/
MODELS = {
    "XM430-W210": MotorModel(1030, "Present Current", "Present Current [mA]", 2.69),
    "XM430-W350": MotorModel(1020, "Present Current", "Present Current [mA]", 2.69),
    "XL430-W250": MotorModel(1060, "Present Load", "Present Load [%]", 0.1),
}

CONDITIONS = {
    "normal": "정상", "overvoltage": "과전압", "undervoltage": "과소전압",
    "overload": "과부하", "undercurrent": "과소전류", "friction": "마찰",
    "gear_backlash": "기어 백래시",
}


@dataclass(frozen=True)
class ExperimentConfig:
    motor_name: str
    port: str
    baudrate: int
    motor_id: int
    protocol_version: float
    turns: float
    direction: int
    acceleration_ms: int
    profile_duration_ms: int
    top_dwell_sec: float
    bottom_dwell_sec: float
    max_cycles: int
    sample_interval_sec: float
    print_interval_sec: float
    flush_every_rows: int
    move_timeout_sec: float
    position_tolerance_pulse: int
    torque_off_on_normal_exit: bool
    condition_name: str
    load_kg: float

    @property
    def model(self):
        return MODELS[self.motor_name]

    @property
    def output_dir(self):
        return PROJECT_ROOT / "results" / "raw" / self.motor_name / self.condition_folder

    @property
    def condition_folder(self):
        if self.condition_name == "overload":
            # 500과 500.0은 동일하게, 소수 부하량은 반올림 없이 폴더명에 기록합니다.
            amount = format(Decimal(str(self.load_kg)), "f")
            if "." in amount:
                amount = amount.rstrip("0").rstrip(".")
            return f"overload_{amount}kg"
        return self.condition_name

    @property
    def travel_pulses(self):
        return self.direction * round(self.turns * 4096)

    def snapshot(self):
        return asdict(self)

    def validate(self):
        if not isinstance(self.condition_name, str) or self.condition_name not in CONDITIONS:
            raise ValueError(f"condition.name must be one of: {', '.join(CONDITIONS)}")
        if type(self.load_kg) not in (int, float) or not math.isfinite(self.load_kg) or self.load_kg < 0:
            raise ValueError("condition.load_kg must be a finite nonnegative number")
        if self.condition_name == "overload":
            if self.load_kg == 0:
                raise ValueError("Set condition.load_kg > 0 for overload")
        elif self.load_kg != 0:
            raise ValueError("Set condition.load_kg = 0 for conditions other than overload")
        if len(self.condition_folder) > 80:
            raise ValueError("condition.load_kg is too long for a folder name")
        if self.motor_name not in MODELS:
            raise ValueError(f"motor.name must be one of: {', '.join(MODELS)}")
        if not isinstance(self.port, str) or not self.port.strip():
            raise ValueError("motor.port must be a nonempty string")
        integer_ranges = {
            "baudrate": (1, 4500000), "motor_id": (0, 252),
            "direction": (-1, 1), "acceleration_ms": (1, 32737),
            "profile_duration_ms": (1, 32767), "max_cycles": (0, 1000000000),
            "flush_every_rows": (1, 1000000), "position_tolerance_pulse": (0, 1048575),
        }
        for key, (low, high) in integer_ranges.items():
            value = getattr(self, key)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{key} must be an integer in {low}..{high}")
        if self.baudrate not in {9600, 57600, 115200, 1000000, 2000000, 3000000, 4000000, 4500000}:
            raise ValueError("Unsupported motor baudrate")
        if type(self.protocol_version) not in (int, float) or self.protocol_version != 2.0:
            raise ValueError("These experiments require Protocol 2.0")
        if self.direction not in (-1, 1):
            raise ValueError("direction must be 1 or -1")
        for key in ("turns", "sample_interval_sec", "print_interval_sec", "move_timeout_sec",
                    "top_dwell_sec", "bottom_dwell_sec"):
            value = getattr(self, key)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"{key} must be a finite number")
            allow_zero = key in ("top_dwell_sec", "bottom_dwell_sec")
            if value < 0 or (value == 0 and not allow_zero):
                raise ValueError(f"{key} must be {'nonnegative' if allow_zero else 'positive'}")
        if self.turns > 2097150 / 4096 or not 1 <= abs(self.travel_pulses) <= 2097150:
            raise ValueError("turns is outside the supported position travel range")
        if self.acceleration_ms * 2 > self.profile_duration_ms:
            raise ValueError("acceleration_ms must not exceed half of profile_duration_ms")
        if self.move_timeout_sec <= self.profile_duration_ms / 1000:
            raise ValueError("move_timeout_sec must exceed the profile duration")
        if type(self.torque_off_on_normal_exit) is not bool:
            raise ValueError("torque_off_on_normal_exit must be true or false")
        return self


def load_config(path=DEFAULT_CONFIG):
    # UTF-8 BOM을 포함한 Windows 편집 파일도 읽습니다.
    data = tomllib.loads(Path(path).read_text(encoding="utf-8-sig"))
    sections = {
        "motor": {"name", "port", "baudrate", "id", "protocol_version"},
        "condition": {"name", "load_kg"},
        "experiment": {"turns", "direction", "acceleration_ms", "profile_duration_ms",
                       "top_dwell_sec", "bottom_dwell_sec", "max_cycles"},
        "logging": {"sample_interval_sec", "print_interval_sec", "flush_every_rows"},
        "control": {"move_timeout_sec", "position_tolerance_pulse", "torque_off_on_normal_exit"},
    }
    if set(data) != set(sections):
        raise ValueError(f"Config sections must be: {', '.join(sections)}")
    for section, keys in sections.items():
        if not isinstance(data[section], dict) or set(data[section]) != keys:
            raise ValueError(f"Check [{section}] keys; required: {', '.join(sorted(keys))}")
    motor = data["motor"]
    condition = data["condition"]
    return ExperimentConfig(
        motor_name=motor["name"], port=motor["port"], baudrate=motor["baudrate"],
        motor_id=motor["id"], protocol_version=motor["protocol_version"],
        condition_name=condition["name"], load_kg=condition["load_kg"],
        **data["experiment"], **data["logging"], **data["control"],
    ).validate()
