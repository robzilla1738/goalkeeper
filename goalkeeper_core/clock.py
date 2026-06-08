"""Time helpers (isolated for testability)."""
from __future__ import annotations

import datetime as _dt


def now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
