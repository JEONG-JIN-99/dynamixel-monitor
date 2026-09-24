from dataclasses import dataclass
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config" / "dashboard.toml"


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8000
    manifest_path: Path = ROOT / "runtime" / "current_experiment.json"
    data_root: Path = ROOT / "runtime" / "standalone_runs"
    mock_data_root: Path = ROOT / "runtime" / "mock_runs"
    poll_interval_sec: float = 0.1
    retention_sec: float = 60
    max_samples: int = 12000
    subscriber_queue_size: int = 32

    @property
    def experiment_data_root(self):
        return self.mock_data_root.parent / "experiment_runs"

    @property
    def control_root(self):
        return self.mock_data_root.parent / "control"

    @classmethod
    def load(cls, path=DEFAULT_CONFIG):
        path = Path(path).resolve()
        with path.open("rb") as handle:
            values = tomllib.load(handle)
        for key in ("manifest_path", "data_root", "mock_data_root"):
            if key in values:
                values[key] = (path.parent / values[key]).resolve()
        result = cls(**values)
        if not 1 <= result.port <= 65535 or not 0.02 <= result.poll_interval_sec <= 10:
            raise ValueError("Invalid server port or polling interval")
        if result.retention_sec != 60 or result.max_samples < 601 or result.subscriber_queue_size < 2:
            raise ValueError("Use a 60-second window, at least 601 samples and queue size >= 2")
        return result
