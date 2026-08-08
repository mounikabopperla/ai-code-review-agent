"""
backend/ingestion/repo_loader.py
----------------------------------
Handles the "get the repo onto disk" step for the /index endpoint --
either validating a local folder path, or cloning a GitHub URL into a
temporary folder.

This is deliberately kept separate from chunk_code.py: repo_loader's
only job is "get me a real local folder path to a repo." What happens
to that folder afterward (chunking, embedding) is someone else's job --
same separation-of-responsibility principle used throughout this project.
"""

import logging
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger("repo-loader")

# Basic sanity check for GitHub URLs -- not exhaustive, just enough to
# reject obviously-wrong input before we try to shell out to git.
GITHUB_URL_PATTERN = re.compile(
    r"^https://github\.com/[\w.-]+/[\w.-]+(\.git)?/?$"
)


class RepoLoadError(Exception):
    """Raised when a local path or GitHub URL can't be turned into a usable repo folder."""
    pass


def validate_local_path(path_str: str) -> Path:
    """
    Validates that a given string is a real, existing, non-empty local
    folder. Raises RepoLoadError with a clear message if not -- this is
    what the API layer will show to the user, so the message matters.
    """
    path = Path(path_str).expanduser().resolve()

    if not path.exists():
        raise RepoLoadError(f"Path does not exist: {path}")
    if not path.is_dir():
        raise RepoLoadError(f"Path is not a folder: {path}")

    has_python_files = any(path.rglob("*.py"))
    if not has_python_files:
        raise RepoLoadError(f"No Python files found in: {path}")

    return path


def is_valid_github_url(url: str) -> bool:
    return bool(GITHUB_URL_PATTERN.match(url.strip()))


def clone_github_repo(url: str, timeout_seconds: int = 120) -> Path:
    """
    Clones a GitHub repo into a fresh temporary folder and returns its path.
    Raises RepoLoadError on any failure (bad URL, network issue, repo not
    found, clone timeout) with a message suitable for showing to the user.

    The caller is responsible for calling cleanup_temp_repo() when done
    with this folder -- temp clones should not accumulate forever.
    """
    url = url.strip()
    if not is_valid_github_url(url):
        raise RepoLoadError(
            f"That doesn't look like a valid GitHub repository URL: {url} "
            f"(expected something like https://github.com/user/repo)"
        )

    temp_dir = Path(tempfile.mkdtemp(prefix="code_review_agent_clone_"))
    logger.info(f"Cloning {url} into {temp_dir}")

    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(temp_dir)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RepoLoadError(f"Cloning timed out after {timeout_seconds} seconds: {url}")

    if result.returncode != 0:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RepoLoadError(f"Failed to clone {url}: {result.stderr.strip()}")

    has_python_files = any(temp_dir.rglob("*.py"))
    if not has_python_files:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RepoLoadError(f"No Python files found in repository: {url}")

    logger.info(f"Successfully cloned {url} -> {temp_dir}")
    return temp_dir


def cleanup_temp_repo(path: Path):
    """Removes a temporary cloned repo folder. Safe to call even if the
    folder doesn't exist or was already removed."""
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
        logger.info(f"Cleaned up temporary clone: {path}")
