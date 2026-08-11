"""Pytest bootstrap for mirror_core tests.

The shared ``_*_helpers`` modules live in this directory. When the full
monorepo suite runs, other packages' conftest files (e.g. Django's
``django.setup()``) are imported before these test modules, and pytest's
prepend import mode does not reliably put this directory on ``sys.path``.
Insert it explicitly so ``from _execution_semantics_helpers import ...``
resolves regardless of collection order.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
