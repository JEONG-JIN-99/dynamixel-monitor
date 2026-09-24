"""Load this folder as a package, independent of its location or directory name."""
import importlib.util
from pathlib import Path
import sys


def load_package():
    name = "motor_dashboard"
    if name not in sys.modules:
        root = Path(__file__).resolve().parent
        spec = importlib.util.spec_from_file_location(name, root / "__init__.py",
                                                     submodule_search_locations=[str(root)])
        package = importlib.util.module_from_spec(spec)
        sys.modules[name] = package
        spec.loader.exec_module(package)
    return name
