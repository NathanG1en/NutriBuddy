# backend/services/cache.py
"""Simple caching utilities."""

import json
from pathlib import Path
from typing import Optional, Any
from functools import wraps


class FileCache:
    """JSON-based file cache (safer than pickle)."""

    def __init__(self, path: str = ".cache/food_cache.json"):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            return json.loads(self._path.read_text())
        return {}

    def _save(self):
        self._path.write_text(json.dumps(self._data))

    def get(self, key: str) -> Optional[Any]:
        return self._data.get(key)

    def set(self, key: str, value: Any):
        self._data[key] = value
        self._save()