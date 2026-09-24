"""Run tests from either the repository or a standalone dashboard folder."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import load_package
load_package()
