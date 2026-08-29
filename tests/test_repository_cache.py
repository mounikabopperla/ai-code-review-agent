"""
tests/test_repository_cache.py
------------------------------
Tests the SQLite repository cache used to avoid
re-indexing unchanged GitHub repositories.
"""

import sys
from pathlib import Path

import pytest


# Add the project root to Python's import path
# so "backend" can be imported during tests.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


import backend.storage.repository_cache as repository_cache


@pytest.fixture
def isolated_cache(tmp_path, monkeypatch):
    """
    Redirects the repository cache to a temporary
    SQLite database so tests never touch real data.
    """

    test_database = (
        tmp_path
        / "test_repository_cache.db"
    )

    monkeypatch.setattr(
        repository_cache,
        "DATABASE_PATH",
        test_database,
    )

    repository_cache.initialize_database()

    return test_database


def test_initialize_database_creates_database_file(
    isolated_cache,
):
    """
    Database initialization should create
    the SQLite file.
    """

    assert isolated_cache.exists()


def test_uncached_repository_returns_none(
    isolated_cache,
):
    """
    A repository that has never been analyzed
    should not have a cache entry.
    """

    result = (
        repository_cache.get_cached_repository(
            "https://github.com/example/project.git"
        )
    )

    assert result is None


def test_save_repository_creates_cache_entry(
    isolated_cache,
):
    """
    Saving an analyzed repository should make
    its metadata available from the cache.
    """

    repository_cache.save_repository(
        repository_url=(
            "https://github.com/example/project.git"
        ),
        repository_name="project",
        commit_sha="abc123",
        collection_name="repo_project",
        status="completed",
        chunks_indexed=42,
    )

    cached = (
        repository_cache.get_cached_repository(
            "https://github.com/example/project.git"
        )
    )

    assert cached is not None

    assert (
        cached["repository_name"]
        == "project"
    )

    assert (
        cached["commit_sha"]
        == "abc123"
    )

    assert (
        cached["collection_name"]
        == "repo_project"
    )

    assert (
        cached["status"]
        == "completed"
    )

    assert (
        cached["chunks_indexed"]
        == 42
    )

    assert cached["analyzed_at"]


def test_saving_same_repository_updates_existing_entry(
    isolated_cache,
):
    """
    Saving the same repository URL again should
    update the existing row rather than creating
    a duplicate.
    """

    repository_url = (
        "https://github.com/example/project.git"
    )

    repository_cache.save_repository(
        repository_url=repository_url,
        repository_name="project",
        commit_sha="old-commit",
        collection_name="repo_project",
        status="completed",
        chunks_indexed=20,
    )

    repository_cache.save_repository(
        repository_url=repository_url,
        repository_name="project",
        commit_sha="new-commit",
        collection_name="repo_project",
        status="completed",
        chunks_indexed=50,
    )

    cached = (
        repository_cache.get_cached_repository(
            repository_url
        )
    )

    assert cached is not None

    assert (
        cached["commit_sha"]
        == "new-commit"
    )

    assert (
        cached["chunks_indexed"]
        == 50
    )


def test_different_repositories_are_stored_separately(
    isolated_cache,
):
    """
    Cache entries for different repository URLs
    should remain independent.
    """

    repository_cache.save_repository(
        repository_url=(
            "https://github.com/example/one.git"
        ),
        repository_name="one",
        commit_sha="commit-one",
        collection_name="repo_one",
        status="completed",
        chunks_indexed=10,
    )

    repository_cache.save_repository(
        repository_url=(
            "https://github.com/example/two.git"
        ),
        repository_name="two",
        commit_sha="commit-two",
        collection_name="repo_two",
        status="completed",
        chunks_indexed=25,
    )

    first = (
        repository_cache.get_cached_repository(
            "https://github.com/example/one.git"
        )
    )

    second = (
        repository_cache.get_cached_repository(
            "https://github.com/example/two.git"
        )
    )

    assert first is not None
    assert second is not None

    assert (
        first["repository_name"]
        == "one"
    )

    assert (
        first["commit_sha"]
        == "commit-one"
    )

    assert (
        second["repository_name"]
        == "two"
    )

    assert (
        second["commit_sha"]
        == "commit-two"
    )