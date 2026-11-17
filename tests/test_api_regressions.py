"""Exercise the production API without calling an external model."""
import os
os.environ.setdefault("GOOGLE_API_KEY", "test-only-key")
os.environ.setdefault("GEMINI_MODEL", "test-only-model")

import pytest
from fastapi.testclient import TestClient
from backend.api import main, indexing_routes


def test_overview_returns_the_frontend_contract(monkeypatch):
    monkeypatch.setattr(main, "generate_project_overview", lambda *args: "Overview text")
    response = TestClient(main.app).post("/project/overview", json={
        "repo_path": "https://github.com/example/project", "explanation_mode": "beginner",
    })
    assert response.status_code == 200
    assert response.json() == {"overview": "Overview text", "explanation_mode": "beginner"}


def test_vercel_cors_preflight():
    response = TestClient(main.app).options("/index", headers={
        "Origin": "https://ai-code-review-agent-omega.vercel.app",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://ai-code-review-agent-omega.vercel.app"


@pytest.mark.parametrize("url", [
    "https://github.com/a/..", "https://github.com/a/.",
    "https://github.com/a/b/tree/main", "https://github.com/a/b?x=1",
    "https://github.com.evil.example/a/b", "https://github.com/a/%2e%2e",
])
def test_malformed_url_rejected_before_clone(url, monkeypatch):
    monkeypatch.setattr(indexing_routes.subprocess, "run", lambda *a, **k: pytest.fail("Git must not run"))
    with pytest.raises(ValueError):
        indexing_routes.clone_github_repository(url)


def test_owner_identity_and_url_variants():
    name = indexing_routes.repository_name_from_url
    assert name("https://github.com/alice/project") != name("https://github.com/bob/project")
    assert name("https://github.com/alice/project.git/") == name("https://github.com/Alice/Project")


def test_cache_does_not_reuse_missing_vectors(monkeypatch):
    class MissingClient:
        def collection_exists(self, name): return False
    monkeypatch.setattr(indexing_routes, "get_qdrant_client", lambda: MissingClient())
    assert not indexing_routes.collection_is_available("repo_missing", 10)


def test_public_index_rejects_local_paths(monkeypatch):
    monkeypatch.delenv("ALLOW_LOCAL_REPOSITORIES", raising=False)
    response = TestClient(main.app).post("/index", json={"repo_path": "/app"})
    assert response.status_code == 400


def test_invalid_overview_url_returns_client_error():
    response = TestClient(main.app).post("/project/overview", json={"repo_path": "https://github.com/owner/.."})
    assert response.status_code == 400
