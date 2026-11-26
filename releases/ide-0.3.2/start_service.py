"""Start the released local service using this Python interpreter."""
from pathlib import Path
import runpy
import sys

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / "service"))
runpy.run_path(str(root / "run_service.py"), run_name="__main__")
