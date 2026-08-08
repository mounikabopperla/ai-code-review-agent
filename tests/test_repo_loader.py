"""
tests/test_repo_loader.py
---------------------------
Tests repo_loader.py's local path validation and GitHub cloning logic.
Includes a REAL test that actually clones a small real public repo --
not mocked -- to genuinely prove the cloning logic works, alongside
fast, mocked tests for error paths that don't need real network calls.

Run with:  pytest tests/test_repo_loader.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import pytest
from ingestion.repo_loader import (
    RepoLoadError,
    validate_local_path,
    is_valid_github_url,
    clone_github_repo,
    cleanup_temp_repo,
)


# ---------------------------------------------------------------
# Local path validation (fast, no network)
# ---------------------------------------------------------------
def test_valid_local_path_with_python_files(tmp_path):
    (tmp_path / "example.py").write_text("def hello(): pass")
    result = validate_local_path(str(tmp_path))
    assert result == tmp_path.resolve()


def test_nonexistent_path_raises_clear_error():
    with pytest.raises(RepoLoadError, match="does not exist"):
        validate_local_path("/this/path/definitely/does/not/exist/anywhere")


def test_path_that_is_a_file_not_folder_raises(tmp_path):
    file_path = tmp_path / "not_a_folder.txt"
    file_path.write_text("hello")
    with pytest.raises(RepoLoadError, match="not a folder"):
        validate_local_path(str(file_path))


def test_folder_with_no_python_files_raises(tmp_path):
    (tmp_path / "readme.txt").write_text("no python here")
    with pytest.raises(RepoLoadError, match="No Python files"):
        validate_local_path(str(tmp_path))


# ---------------------------------------------------------------
# GitHub URL validation (fast, no network)
# ---------------------------------------------------------------
def test_valid_github_urls_are_accepted():
    assert is_valid_github_url("https://github.com/psf/requests")
    assert is_valid_github_url("https://github.com/psf/requests.git")
    assert is_valid_github_url("https://github.com/pallets/click/")


def test_invalid_github_urls_are_rejected():
    assert not is_valid_github_url("not a url at all")
    assert not is_valid_github_url("https://gitlab.com/someone/something")
    assert not is_valid_github_url("github.com/missing/scheme")
    assert not is_valid_github_url("")


def test_clone_rejects_invalid_url_without_touching_network():
    with pytest.raises(RepoLoadError, match="doesn't look like a valid"):
        clone_github_repo("not-a-real-url")


# ---------------------------------------------------------------
# REAL cloning test -- actually hits GitHub, no mocking
# ---------------------------------------------------------------
def test_real_clone_of_small_public_repo():
    """
    This test genuinely clones a real, small public repo from GitHub.
    Using octocat/Hello-World -- GitHub's own tiny demo repo, about as
    small and stable as a real test target gets.

    Note: this repo has no .py files, so we expect our own "no Python
    files found" check to correctly reject it -- which is itself a
    useful real-world case (someone points the tool at a non-Python repo).
    """
    with pytest.raises(RepoLoadError, match="No Python files"):
        clone_github_repo("https://github.com/octocat/Hello-World.git")


def test_real_clone_of_actual_python_repo_and_cleanup():
    """
    Clones a real, small, genuinely Python repo, confirms Python files
    exist on disk, then cleans up -- proving the full real cycle works.
    Using a small, stable public Python utility repo.
    """
    repo_path = clone_github_repo("https://github.com/kennethreitz/tablib.git")
    try:
        assert repo_path.exists()
        py_files = list(repo_path.rglob("*.py"))
        assert len(py_files) > 0
        print(f"\nCloned real repo with {len(py_files)} real Python files")
    finally:
        cleanup_temp_repo(repo_path)
        assert not repo_path.exists()  # confirm cleanup actually worked
