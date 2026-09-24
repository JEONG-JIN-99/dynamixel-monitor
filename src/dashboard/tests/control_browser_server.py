"""Isolated idle server for the control/log browser tests; no hardware."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import load_package
load_package()
import uvicorn
from motor_dashboard.main import create_app
from motor_dashboard.settings import Settings
with tempfile.TemporaryDirectory(prefix="motor-control-browser-") as directory:
    root=Path(directory)
    uvicorn.run(create_app(Settings(manifest_path=root/"current.json",data_root=root/"original",mock_data_root=root/"mock_runs")),host="127.0.0.1",port=8766,log_level="warning")
