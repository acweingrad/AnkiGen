"""
Stub out Anki's `aqt` and `anki` modules so core/ and tests/ can be imported
and tested with a plain Python interpreter (no Anki installation required).
"""
import sys
from types import ModuleType
from unittest.mock import MagicMock


def _make_stub(*parts):
    """Build a chain of MagicMock modules under sys.modules."""
    for i in range(1, len(parts) + 1):
        name = ".".join(parts[:i])
        if name not in sys.modules:
            sys.modules[name] = MagicMock()


for mod in [
    "aqt",
    "aqt.qt",
    "aqt.utils",
    "aqt.operations",
    "anki",
    "anki.notes",
    "anki.collection",
]:
    _make_stub(*mod.split("."))
