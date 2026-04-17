from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


LAB_ROOT = Path(__file__).resolve().parents[1] / "06-lab-complete"
APP_MAIN = LAB_ROOT / "app" / "main.py"

if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

spec = importlib.util.spec_from_file_location("lab6_app_main", APP_MAIN)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Unable to load app module from {APP_MAIN}")

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

app = module.app