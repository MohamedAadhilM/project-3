"""Locate the repository root so every file runs from IDLE, Jupyter or the terminal."""
import sys
from pathlib import Path

try:
    _here = Path(__file__).resolve().parent
except NameError:
    _here = Path.cwd()
ROOT = next(p for p in [_here, *_here.parents] if (p / "src" / "fg").exists())
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
