"""Pytest bootstrap — make `src/sange` importable without `pip install -e`.

Sange uses the `src/` layout (per Simtabi org CLAUDE.md), which keeps the
package out of the import path by default. That's the correct production
posture, but local-test ergonomics suffer: `pytest` from the repo root
can't `import sange` until the package is installed.

This conftest injects `src/` at sys.path[0] so tests run identically on a
fresh clone (`pytest`) and inside an editable install (`pip install -e .;
pytest`). The install-once path still works; this just removes the
mandatory step.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
