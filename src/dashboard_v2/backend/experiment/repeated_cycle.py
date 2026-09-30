"""Run the standalone repeated-cycle experiment."""
import sys
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from bootstrap import load_package
    load_package()
from motor_dashboard.experiment.acquisition import main

if __name__ == "__main__":
    raise SystemExit(main())
