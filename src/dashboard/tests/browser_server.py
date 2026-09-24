"""Isolated CSV fixture server used only by Playwright. Never imports SDK."""
from datetime import datetime, timedelta
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import load_package
load_package()
import uvicorn
from motor_dashboard.tests.test_pipeline import setup_source, row, csv_bytes
from motor_dashboard.file_lock import FileLock
from motor_dashboard.main import create_app

with tempfile.TemporaryDirectory(prefix="motor-dashboard-browser-") as temporary:
    root = Path(temporary)
    start = datetime.now().astimezone() - timedelta(seconds=65)
    def sample(index):
        t = index / 10
        return row(t, **{
            "PC Time": (start + timedelta(seconds=t)).replace(tzinfo=None).isoformat(timespec="milliseconds"),
            "Present Position": str(round(2048 + 2048 * math.sin(t * 0.45))),
            "Position Trajectory": str(round(2048 + 2048 * math.sin(t * 0.45) + 15)),
            "Goal Position": "4096" if math.cos(t * 0.45) > 0 else "0",
            "Present Current": str(round(100 + 70 * math.sin(t))),
            "Present Velocity": str(round(40 * math.cos(t * 0.45))),
            "Condition": "SIMULATED",
        })
    settings, manifest, path = setup_source(root, [sample(i) for i in range(651)], status="running")
    Path(manifest["metadataPath"]).write_text(json.dumps({
        "created_at": start.isoformat(), "simulated": True,
        "settings": {"baudrate": 57600, "protocol_version": 2},
        "model_number": 1030, "firmware_version": None,
    }))
    lock = FileLock(settings.manifest_path.with_suffix(".lock")).acquire()
    stop = threading.Event()
    def produce():
        index = 651
        while not stop.wait(2):
            with path.open("ab") as output:
                output.write(csv_bytes([sample(i) for i in range(index, index + 20)], False))
            index += 20
    thread = threading.Thread(target=produce, daemon=True)
    thread.start()
    try:
        uvicorn.run(create_app(settings, mock_prehistory_ms=int(os.environ.get("DASHBOARD_TEST_HISTORY_MS", "125000"))), host="127.0.0.1", port=8765, log_level="warning")
    finally:
        stop.set()
        thread.join()
        lock.release()
