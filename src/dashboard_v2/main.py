"""Stable launcher: python main.py from any working directory."""
if __package__:
    from .bootstrap import load_package
else:
    from bootstrap import load_package

load_package()
from motor_dashboard.app import create_app, create_single_app, main

if __name__ == "__main__":
    main()
