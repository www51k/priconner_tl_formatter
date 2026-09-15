"""互換用エントリポイント。共通実装は :mod:`priconner_tl.common` を正本とする。"""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from priconner_tl.common import *  # noqa: F401,F403,E402
