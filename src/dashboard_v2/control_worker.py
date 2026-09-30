"""Dedicated SDK process; started only by an explicit real experiment request."""
import argparse
import sys
from pathlib import Path
if not __package__:
    from bootstrap import load_package
    __package__ = load_package()
from .run_repository import atomic_json
from .experiment.configuration import load_config

def main():
    parser = argparse.ArgumentParser()
    for name in ("config", "directory", "run-id", "manifest"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    from .experiment.acquisition import Experiment
    experiment = Experiment(load_config(args.config), args.config, run_directory=args.directory,
                            run_id=args.run_id, manifest_path=args.manifest)
    code = experiment.run()
    atomic_json(Path(args.directory)/"result.json", {"code":code,"completedCycles":experiment.completed_cycles})
    return code

if __name__ == "__main__":
    raise SystemExit(main())
