# backend/services/cache.py
"""
High-performance SQLite embedded cache with WAL mode, atomic writes,
TTL expiration, and thread-safe connection pooling.
"""

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SQLiteCache:
    """
    Thread-safe embedded SQLite cache with Write-Ahead Logging (WAL) mode.
    Provides sub-millisecond atomic key-value operations with TTL expiration support.
    """

    def __init__(
        self,
        db_path: str = "backend/data/cache.db",
        default_ttl_seconds: Optional[int] = None,  # None means persistent
        migrate_legacy: bool = True,
    ):
        self._db_path = Path(db_path)
        if str(db_path) != ":memory:":
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._default_ttl = default_ttl_seconds
        self._local = threading.local()

        self._init_db()
        if migrate_legacy:
            self._migrate_legacy_json_cache()

    def _get_connection(self) -> sqlite3.Connection:
        """Return a thread-local SQLite connection configured for high concurrency."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(
                str(self._db_path),
                timeout=30.0,
                check_same_thread=False,
            )
            # High-performance pragmas for concurrent reads & writes
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self):
        """Create cache tables and indexes if they do not exist."""
        conn = self._get_connection()
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kv_cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_kv_cache_expires_at 
                ON kv_cache(expires_at);
                """
            )

    def _migrate_legacy_json_cache(self):
        """Migrate any existing .cache/food_cache.json into SQLite seamlessly."""
        legacy_path = Path(".cache/food_cache.json")
        if legacy_path.exists():
            try:
                data = json.loads(legacy_path.read_text())
                if isinstance(data, dict) and data:
                    logger.info(
                        f"Migrating {len(data)} cached items from {legacy_path} to SQLite..."
                    )
                    now = time.time()
                    conn = self._get_connection()
                    with conn:
                        for k, v in data.items():
                            conn.execute(
                                """
                                INSERT OR REPLACE INTO kv_cache (key, value, created_at, expires_at)
                                VALUES (?, ?, ?, ?)
                                """,
                                (k, json.dumps(v), now, None),
                            )
                    logger.info("Legacy cache migration completed successfully.")
            except Exception as e:
                logger.warning(f"Could not migrate legacy JSON cache: {e}")

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value by key. Returns None if missing or expired."""
        conn = self._get_connection()
        now = time.time()
        try:
            cursor = conn.execute(
                "SELECT value, expires_at FROM kv_cache WHERE key = ?", (key,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            val_str, expires_at = row
            if expires_at is not None and expires_at < now:
                # Expired: delete lazily
                self.delete(key)
                return None

            return json.loads(val_str)
        except Exception as e:
            logger.error(f"Cache get error for key '{key}': {e}")
            return None

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        """Store a JSON-serializable value in the cache with optional TTL."""
        conn = self._get_connection()
        now = time.time()
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        expires_at = (now + ttl) if ttl is not None else None

        try:
            val_str = json.dumps(value)
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO kv_cache (key, value, created_at, expires_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (key, val_str, now, expires_at),
                )
        except Exception as e:
            logger.error(f"Cache set error for key '{key}': {e}")

    def has(self, key: str) -> bool:
        """Check if an unexpired key exists."""
        return self.get(key) is not None

    def delete(self, key: str) -> bool:
        """Delete a key from the cache."""
        conn = self._get_connection()
        try:
            with conn:
                cursor = conn.execute("DELETE FROM kv_cache WHERE key = ?", (key,))
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Cache delete error for key '{key}': {e}")
            return False

    def clear(self, expired_only: bool = False):
        """Clear all entries or only expired entries."""
        conn = self._get_connection()
        now = time.time()
        try:
            with conn:
                if expired_only:
                    conn.execute(
                        "DELETE FROM kv_cache WHERE expires_at IS NOT NULL AND expires_at < ?",
                        (now,),
                    )
                else:
                    conn.execute("DELETE FROM kv_cache")
        except Exception as e:
            logger.error(f"Cache clear error: {e}")

    def get_stats(self) -> dict:
        """Return cache statistics."""
        conn = self._get_connection()
        now = time.time()
        try:
            total = conn.execute("SELECT COUNT(*) FROM kv_cache").fetchone()[0]
            expired = conn.execute(
                "SELECT COUNT(*) FROM kv_cache WHERE expires_at IS NOT NULL AND expires_at < ?",
                (now,),
            ).fetchone()[0]
            return {
                "total_items": total,
                "active_items": total - expired,
                "expired_items": expired,
                "db_path": str(self._db_path),
            }
        except Exception as e:
            logger.error(f"Cache stats error: {e}")
            return {"error": str(e)}


# Backward-compatible alias for existing code
FileCache = SQLiteCache