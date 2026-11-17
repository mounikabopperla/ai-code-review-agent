"""Bounded, expiring answer cache; failures never prevent answering a question."""
import hashlib
import json
import logging
import os
import sqlite3
import time
from pathlib import Path

DATABASE_PATH = Path(os.getenv("ANSWER_CACHE_PATH", "answer_cache.db"))
TTL_SECONDS = 24 * 60 * 60
MAX_ENTRIES = 1000
PROMPT_VERSION = "grounded-v2"
logger = logging.getLogger(__name__)


def cache_key(prompt: str, model: str, namespace: str = "") -> str:
    # The full prompt includes question, mode, and retrieved code. Namespace
    # adds repository identity/commit to invalidate even unchanged excerpts.
    payload = [PROMPT_VERSION, namespace, model, prompt]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode()).hexdigest()


def _connect():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=5)
    connection.execute("CREATE TABLE IF NOT EXISTS answers (key TEXT PRIMARY KEY, answer TEXT NOT NULL, expires REAL NOT NULL, created REAL NOT NULL)")
    return connection


def get_answer(key: str) -> str | None:
    try:
        with _connect() as connection:
            row = connection.execute("SELECT answer FROM answers WHERE key = ? AND expires > ?", (key, time.time())).fetchone()
        return row[0] if row else None
    except (sqlite3.Error, OSError):
        logger.warning("Answer cache unavailable; generating a fresh answer")
        return None


def save_answer(key: str, answer: str) -> None:
    if not answer.strip():
        return
    try:
        now = time.time()
        with _connect() as connection:
            connection.execute("DELETE FROM answers WHERE expires <= ?", (now,))
            connection.execute("INSERT OR REPLACE INTO answers VALUES (?, ?, ?, ?)", (key, answer, now + TTL_SECONDS, now))
            connection.execute("DELETE FROM answers WHERE key IN (SELECT key FROM answers ORDER BY created DESC LIMIT -1 OFFSET ?)", (MAX_ENTRIES,))
    except (sqlite3.Error, OSError):
        logger.warning("Could not cache answer; response remains available")
