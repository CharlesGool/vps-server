"""Unit tests. Importing the package isolates them from an installed console (see _isolation)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _isolation  # noqa: E402,F401
