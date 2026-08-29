import sqlite3
from pathlib import Path
from datetime import datetime, timezone


DATABASE_PATH = Path("repository_cache.db")


def get_connection() -> sqlite3.Connection:
    """
    Opens a connection to the local SQLite cache database.
    """

    connection = sqlite3.connect(DATABASE_PATH)

    connection.row_factory = sqlite3.Row

    return connection


def initialize_database() -> None:
    """
    Creates the repository cache table if it does not exist.
    """

    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS repositories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repository_url TEXT UNIQUE NOT NULL,
                repository_name TEXT NOT NULL,
                commit_sha TEXT,
                collection_name TEXT NOT NULL,
                status TEXT NOT NULL,
                chunks_indexed INTEGER DEFAULT 0,
                analyzed_at TEXT NOT NULL
            )
            """
        )

        connection.commit()


def get_cached_repository(
    repository_url: str,
) -> dict | None:
    """
    Returns cached repository metadata if available.
    """

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT *
            FROM repositories
            WHERE repository_url = ?
            """,
            (repository_url,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)


def save_repository(
    *,
    repository_url: str,
    repository_name: str,
    commit_sha: str | None,
    collection_name: str,
    status: str,
    chunks_indexed: int,
) -> None:
    """
    Inserts or updates repository cache metadata.
    """

    analyzed_at = datetime.now(
        timezone.utc
    ).isoformat()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO repositories (
                repository_url,
                repository_name,
                commit_sha,
                collection_name,
                status,
                chunks_indexed,
                analyzed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(repository_url)
            DO UPDATE SET
                repository_name = excluded.repository_name,
                commit_sha = excluded.commit_sha,
                collection_name = excluded.collection_name,
                status = excluded.status,
                chunks_indexed = excluded.chunks_indexed,
                analyzed_at = excluded.analyzed_at
            """,
            (
                repository_url,
                repository_name,
                commit_sha,
                collection_name,
                status,
                chunks_indexed,
                analyzed_at,
            ),
        )

        connection.commit()