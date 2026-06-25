from __future__ import annotations

import sys
import warnings
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


warnings.filterwarnings(
    "ignore",
    message=r".*allowed_objects.*",
    category=Warning,
)
