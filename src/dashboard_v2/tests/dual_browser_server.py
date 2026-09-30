"""An empty isolated two-motor server for browser integration tests."""
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bootstrap import load_package
load_package()
from motor_dashboard.main import create_app
from motor_dashboard.settings import Settings
import uvicorn
with tempfile.TemporaryDirectory(prefix='dashboard-v2-e2e-') as tmp:
    uvicorn.run(create_app(Settings(mock_data_root=Path(tmp)/'mock_runs')),
                host='127.0.0.1',port=8767,log_level='warning')
