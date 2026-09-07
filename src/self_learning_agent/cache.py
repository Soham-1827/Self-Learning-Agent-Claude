"""On-disk cache of raw provider payloads (I2).

Synthesis gets re-run many times while prompts are tuned. Re-fetching each time
is slow, rude to the provider, and makes tests need the network.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]")


def _safe(name: str) -> str:
    return _UNSAFE.sub("_", name)[:120]


class Cache:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def path_for(self, source_type: str, source_id: str, kind: str) -> Path:
        return self.root / _safe(source_type) / f"{_safe(source_id)}.{_safe(kind)}.json"

    def get(self, source_type: str, source_id: str, kind: str) -> Any | None:
        path = self.path_for(source_type, source_id, kind)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None  # a corrupt cache entry is a miss, never an error

    def put(self, source_type: str, source_id: str, kind: str, payload: Any) -> Path:
        path = self.path_for(source_type, source_id, kind)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)  # atomic: never leave a half-written entry
        return path
