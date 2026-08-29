"""
tests/test_indexing_cache_behavior.py
-------------------------------------
Tests repository cache decision behavior.

These tests verify that:

1. A new repository is analyzed normally.
2. An unchanged cached repository skips embeddings.
3. A repository with a new commit is analyzed again.

All expensive GitHub, Voyage, and Qdrant operations
are mocked, so these tests stay fast.
"""

import sys
from pathlib import Path

import pytest


PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent
)

sys.path.insert(
    0,
    str(PROJECT_ROOT),
)


import backend.api.indexing_routes as indexing_routes


TEST_REPOSITORY_URL = (
    "https://github.com/example/project.git"
)

TEST_REPOSITORY_NAME = "project"

TEST_REPOSITORY_PATH = Path(
    "/tmp/project"
)


def create_test_job(job_id: str) -> None:
    """
    Creates the in-memory job entry required by
    update_job().
    """

    indexing_routes.analysis_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "message": "Starting project analysis...",
        "repository_input": TEST_REPOSITORY_URL,
    }


@pytest.fixture(autouse=True)
def clear_analysis_jobs():
    """
    Keeps tests isolated from one another.
    """

    indexing_routes.analysis_jobs.clear()

    yield

    indexing_routes.analysis_jobs.clear()


def test_new_repository_is_analyzed_and_cached(
    monkeypatch,
):
    """
    When a repository is not already cached,
    the application should analyze it,
    generate embeddings, and save cache metadata.
    """

    job_id = "new-repository-job"

    create_test_job(job_id)

    monkeypatch.setattr(
        indexing_routes,
        "clone_github_repository",
        lambda url: TEST_REPOSITORY_PATH,
    )

    monkeypatch.setattr(
        indexing_routes,
        "get_repository_commit_sha",
        lambda repo_path: "commit-123",
    )

    monkeypatch.setattr(
        indexing_routes,
        "get_cached_repository",
        lambda repository_url: None,
    )

    fake_chunks = [
        {
            "chunk_id": "chunk-1",
        },
        {
            "chunk_id": "chunk-2",
        },
    ]

    chunk_calls = []

    def fake_chunk_repository(repo_path):
        chunk_calls.append(repo_path)

        return fake_chunks

    monkeypatch.setattr(
        indexing_routes,
        "chunk_repository",
        fake_chunk_repository,
    )

    embedding_calls = []

    def fake_embed_and_store_chunks(
        chunks,
        repository_name,
    ):
        embedding_calls.append(
            {
                "chunks": chunks,
                "repository_name": repository_name,
            }
        )

        return len(chunks)

    monkeypatch.setattr(
        indexing_routes,
        "embed_and_store_chunks",
        fake_embed_and_store_chunks,
    )

    saved_repositories = []

    def fake_save_repository(**kwargs):
        saved_repositories.append(kwargs)

    monkeypatch.setattr(
        indexing_routes,
        "save_repository",
        fake_save_repository,
    )

    indexing_routes.run_repository_analysis(
        job_id,
        TEST_REPOSITORY_URL,
    )

    job = indexing_routes.analysis_jobs[
        job_id
    ]

    assert job["status"] == "completed"
    assert job["progress"] == 100
    assert job["cached"] is False

    assert len(chunk_calls) == 1
    assert len(embedding_calls) == 1
    assert len(saved_repositories) == 1

    saved = saved_repositories[0]

    assert (
        saved["repository_url"]
        == TEST_REPOSITORY_URL
    )

    assert (
        saved["repository_name"]
        == TEST_REPOSITORY_NAME
    )

    assert (
        saved["commit_sha"]
        == "commit-123"
    )

    assert (
        saved["collection_name"]
        == "repo_project"
    )

    assert saved["status"] == "completed"
    assert saved["chunks_indexed"] == 2


def test_same_commit_reuses_cached_collection(
    monkeypatch,
):
    """
    When the repository URL and commit SHA match
    a completed cache entry, expensive analysis
    should be skipped.
    """

    job_id = "cached-repository-job"

    create_test_job(job_id)

    monkeypatch.setattr(
        indexing_routes,
        "clone_github_repository",
        lambda url: TEST_REPOSITORY_PATH,
    )

    monkeypatch.setattr(
        indexing_routes,
        "get_repository_commit_sha",
        lambda repo_path: "same-commit",
    )

    monkeypatch.setattr(
        indexing_routes,
        "get_cached_repository",
        lambda repository_url: {
            "repository_url": (
                TEST_REPOSITORY_URL
            ),
            "repository_name": (
                TEST_REPOSITORY_NAME
            ),
            "commit_sha": "same-commit",
            "collection_name": "repo_project",
            "status": "completed",
            "chunks_indexed": 120,
        },
    )

    activated_collections = []

    def fake_set_active_collection(
        collection_name,
    ):
        activated_collections.append(
            collection_name
        )

    monkeypatch.setattr(
        indexing_routes,
        "set_active_collection",
        fake_set_active_collection,
    )

    def should_not_chunk(*args, **kwargs):
        pytest.fail(
            "chunk_repository should not run "
            "for an unchanged cached repository."
        )

    def should_not_embed(*args, **kwargs):
        pytest.fail(
            "embed_and_store_chunks should not run "
            "for an unchanged cached repository."
        )

    def should_not_save(*args, **kwargs):
        pytest.fail(
            "save_repository should not run "
            "when the existing cache is reused."
        )

    monkeypatch.setattr(
        indexing_routes,
        "chunk_repository",
        should_not_chunk,
    )

    monkeypatch.setattr(
        indexing_routes,
        "embed_and_store_chunks",
        should_not_embed,
    )

    monkeypatch.setattr(
        indexing_routes,
        "save_repository",
        should_not_save,
    )

    indexing_routes.run_repository_analysis(
        job_id,
        TEST_REPOSITORY_URL,
    )

    job = indexing_routes.analysis_jobs[
        job_id
    ]

    assert job["status"] == "completed"
    assert job["progress"] == 100
    assert job["cached"] is True

    assert job["chunks_indexed"] == 120

    assert activated_collections == [
        "repo_project"
    ]


def test_changed_commit_is_analyzed_again(
    monkeypatch,
):
    """
    When a cached repository exists but its
    commit SHA differs from the current repository,
    the project should be analyzed again.
    """

    job_id = "changed-repository-job"

    create_test_job(job_id)

    monkeypatch.setattr(
        indexing_routes,
        "clone_github_repository",
        lambda url: TEST_REPOSITORY_PATH,
    )

    monkeypatch.setattr(
        indexing_routes,
        "get_repository_commit_sha",
        lambda repo_path: "new-commit",
    )

    monkeypatch.setattr(
        indexing_routes,
        "get_cached_repository",
        lambda repository_url: {
            "repository_url": (
                TEST_REPOSITORY_URL
            ),
            "repository_name": (
                TEST_REPOSITORY_NAME
            ),
            "commit_sha": "old-commit",
            "collection_name": "repo_project",
            "status": "completed",
            "chunks_indexed": 100,
        },
    )

    chunk_calls = []

    def fake_chunk_repository(repo_path):
        chunk_calls.append(repo_path)

        return [
            {
                "chunk_id": "updated-chunk",
            }
        ]

    monkeypatch.setattr(
        indexing_routes,
        "chunk_repository",
        fake_chunk_repository,
    )

    embedding_calls = []

    def fake_embed_and_store_chunks(
        chunks,
        repository_name,
    ):
        embedding_calls.append(
            repository_name
        )

        return 1

    monkeypatch.setattr(
        indexing_routes,
        "embed_and_store_chunks",
        fake_embed_and_store_chunks,
    )

    saved_repositories = []

    def fake_save_repository(**kwargs):
        saved_repositories.append(kwargs)

    monkeypatch.setattr(
        indexing_routes,
        "save_repository",
        fake_save_repository,
    )

    indexing_routes.run_repository_analysis(
        job_id,
        TEST_REPOSITORY_URL,
    )

    job = indexing_routes.analysis_jobs[
        job_id
    ]

    assert job["status"] == "completed"
    assert job["cached"] is False

    assert len(chunk_calls) == 1
    assert len(embedding_calls) == 1
    assert len(saved_repositories) == 1

    saved = saved_repositories[0]

    assert (
        saved["commit_sha"]
        == "new-commit"
    )

    assert saved["chunks_indexed"] == 1