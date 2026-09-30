"""Relocation must not redirect local records or break standalone entry points."""
from pathlib import Path
import subprocess
import sys

from motor_dashboard.settings import ROOT, Settings
from motor_dashboard.experiment.configuration import PROJECT_ROOT, load_config
from motor_dashboard.experiment.run_manifest import DEFAULT_MANIFEST


def test_data_paths_remain_at_dashboard_root():
    assert ROOT == Path(__file__).resolve().parents[2]
    assert PROJECT_ROOT == ROOT
    assert DEFAULT_MANIFEST == ROOT / "runtime/current_experiment.json"
    settings = Settings.load()
    assert settings.mock_data_root == ROOT / "runtime/mock_runs"
    assert settings.manifest_path == DEFAULT_MANIFEST
    assert load_config().output_dir.is_relative_to(ROOT / "runtime")


def test_cli_entry_points_from_another_directory(tmp_path):
    commands = [
        [ROOT / "main.py", "--help"],
        [ROOT / "backend/control/worker.py", "--help"],
        [ROOT / "backend/experiment/repeated_cycle.py", "--check-config"],
    ]
    for command in commands:
        subprocess.run([sys.executable, *map(str, command)], cwd=tmp_path,
                       check=True, capture_output=True, timeout=20)
