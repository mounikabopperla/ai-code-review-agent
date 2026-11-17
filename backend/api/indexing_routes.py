from pathlib import Path

import shutil
import re
import os
import hashlib
import tempfile
from urllib.parse import urlsplit
from threading import Lock
import subprocess
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
)

from pydantic import BaseModel

from backend.ingestion.chunk_code import (
    chunk_repository,
)

from backend.embeddings.embed_chunks import (
    embed_and_store_chunks,
)

from backend.storage.repository_cache import (
    INDEX_SCHEMA_VERSION,
    get_cached_repository,
    initialize_database,
    save_repository,
)

from backend.vector_store.qdrant_store import (
    sanitize_collection_name,
    set_active_collection,
    get_qdrant_client,
)


router = APIRouter()

CLONED_REPOS_DIR = Path("cloned_repos")

initialize_database()


# ---------------------------------------------------------
# Temporary in-memory analysis job storage
#
# Later this can be moved to SQL so job status survives
# server restarts.
# ---------------------------------------------------------

analysis_jobs: dict[str, dict] = {}


class IndexRequest(BaseModel):
    repo_path: str


def is_github_url(value: str) -> bool:
    """
    Returns True when the input looks like
    a GitHub repository URL.
    """

    value = value.strip().lower()

    return (
        value.startswith("https://github.com/")
        or value.startswith("http://github.com/")
    )


def repository_name_from_url(url: str) -> str:
    """Validate a GitHub URL and retain both owner and repository identity."""
    parsed = urlsplit(url.strip())
    if (parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != "github.com"
            or parsed.query or parsed.fragment):
        raise ValueError("Provide a GitHub repository URL: https://github.com/owner/repository")
    parts = parsed.path.strip("/").split("/")
    if len(parts) != 2:
        raise ValueError("Provide a repository URL, not a branch or file URL.")
    owner, name = parts
    if name.endswith(".git"):
        name = name[:-4]
    if any(not re.fullmatch(r"[A-Za-z0-9_.-]+", part) or part in {".", ".."} for part in (owner, name)):
        raise ValueError("Invalid GitHub owner or repository name.")
    identity = f"{owner.lower()}/{name.lower()}"
    digest = hashlib.sha256(identity.encode()).hexdigest()[:12]
    return f"{owner.lower()}_{name.lower()}_{digest}"


def repository_name_from_path(repo_path: Path) -> str:
    digest = hashlib.sha256(str(repo_path.resolve()).encode()).hexdigest()[:12]
    return f"{repo_path.name}_{digest}"


def clone_github_repository(url: str) -> Path:
    repository_name_from_url(url)  # Validate before creating or removing anything.
    CLONED_REPOS_DIR.mkdir(parents=True, exist_ok=True)
    destination = Path(tempfile.mkdtemp(prefix="analysis_", dir=CLONED_REPOS_DIR)).resolve()
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--", url, str(destination)],
            check=True, capture_output=True, text=True, timeout=120,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except Exception as error:
        shutil.rmtree(destination, ignore_errors=True)
        if isinstance(error, subprocess.TimeoutExpired):
            raise RuntimeError("Cloning timed out after 120 seconds.") from error
        raise RuntimeError("Could not clone this public GitHub repository. Check the URL and server logs.") from error
    return destination


def collection_is_available(name: str, expected_count: int) -> bool:
    client = get_qdrant_client()
    return (expected_count > 0 and client.collection_exists(name)
            and client.count(collection_name=name, exact=True).count == expected_count)


def get_remote_commit_sha(url: str) -> str | None:
    """Check HEAD without downloading a repository; fall back to clone on failure."""
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--", url, "HEAD"],
            check=True, capture_output=True, text=True, timeout=20,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        sha = result.stdout.split()[0] if result.stdout.split() else ""
        return sha if re.fullmatch(r"[a-fA-F0-9]{40,64}", sha) else None
    except (OSError, subprocess.SubprocessError):
        return None


def get_repository_commit_sha(
    repo_path: Path,
) -> str:
    """
    Returns the current Git commit SHA
    for a cloned repository.
    """

    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "rev-parse",
                "HEAD",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        return result.stdout.strip()

    except subprocess.CalledProcessError as error:
        raise RuntimeError(
            "Could not determine the repository version."
        ) from error


def update_job(
    job_id: str,
    *,
    status: str,
    progress: int,
    message: str,
    **extra,
):
    """
    Updates the current state of one analysis job.
    """

    analysis_jobs[job_id].update(
        {
            "status": status,
            "progress": progress,
            "message": message,
            **extra,
        }
    )


def _run_repository_analysis(
    job_id: str,
    user_input: str,
):
    """
    Performs repository analysis in the background.

    GitHub repositories are checked against the
    SQLite cache before chunking and BM25 indexing
    work is performed.

    Cached repositories are reused only when:

    1. Previous indexing completed successfully.
    2. The Git commit SHA has not changed.
    3. The index schema matches the current
       BM25 sparse-vector schema.
    """

    repo_path = None
    source_type = None
    repository_name = None
    commit_sha = None

    try:

        # -------------------------------------------------
        # Stage 1 — read project
        # -------------------------------------------------

        update_job(
            job_id,
            status="running",
            progress=10,
            message="Reading the project...",
        )

        if is_github_url(user_input):

            source_type = "github"

            repository_name = (
                repository_name_from_url(
                    user_input
                )
            )

            cached = get_cached_repository(user_input)
            if (cached and cached.get("status") == "completed"
                    and cached.get("index_version") == INDEX_SCHEMA_VERSION
                    and cached.get("commit_sha")
                    and get_remote_commit_sha(user_input) == cached["commit_sha"]
                    and collection_is_available(cached["collection_name"], cached.get("chunks_indexed", 0))):
                set_active_collection(cached["collection_name"])
                update_job(job_id, status="completed", progress=100, message="Project ready",
                           source_type=source_type, repository_name=repository_name,
                           chunks_indexed=cached["chunks_indexed"], cached=True)
                return

            repo_path = clone_github_repository(
                user_input
            )

            commit_sha = (
                get_repository_commit_sha(
                    repo_path
                )
            )

            # ---------------------------------------------
            # Cache check
            # ---------------------------------------------

            cached_repository = (
                get_cached_repository(
                    user_input
                )
            )

            if (
                cached_repository
                and cached_repository.get(
                    "status"
                ) == "completed"
                and cached_repository.get(
                    "commit_sha"
                ) == commit_sha
                and cached_repository.get(
                    "index_version"
                ) == INDEX_SCHEMA_VERSION
                and collection_is_available(cached_repository["collection_name"], cached_repository.get("chunks_indexed", 0))
            ):
                cached_collection = (
                    cached_repository[
                        "collection_name"
                    ]
                )

                set_active_collection(
                    cached_collection
                )

                update_job(
                    job_id,
                    status="completed",
                    progress=100,
                    message="Project ready",
                    source_type=source_type,
                    repository_name=(
                        repository_name
                    ),
                    chunks_indexed=(
                        cached_repository.get(
                            "chunks_indexed",
                            0,
                        )
                    ),
                    cached=True,
                )

                return

        else:

            if os.getenv("ALLOW_LOCAL_REPOSITORIES", "false").lower() != "true":
                raise ValueError("Local paths are disabled on this server. Use a public GitHub repository URL.")
            source_type = "local"

            repo_path = (
                Path(user_input)
                .expanduser()
                .resolve()
            )

            if not repo_path.exists():
                raise ValueError(
                    "Repository path does not exist."
                )

            if not repo_path.is_dir():
                raise ValueError(
                    "The provided path is not "
                    "a directory."
                )

            repository_name = (
                repository_name_from_path(
                    repo_path
                )
            )

        # -------------------------------------------------
        # Stage 2 — understand project
        # -------------------------------------------------

        update_job(
            job_id,
            status="running",
            progress=30,
            message=(
                "Understanding the important "
                "parts..."
            ),
            repository_name=repository_name,
        )

        chunks = chunk_repository(
            str(repo_path)
        )

        if not chunks:
            raise ValueError(
                "No supported project content "
                "was found."
            )

        # -------------------------------------------------
        # Stage 3 — prepare project
        #
        # embed_and_store_chunks now uses local BM25
        # sparse vectors rather than Voyage embeddings.
        # -------------------------------------------------

        update_job(
            job_id,
            status="running",
            progress=55,
            message=(
                "Preparing the project for "
                "your questions..."
            ),
            chunks_found=len(chunks),
        )

        stored_count = (
            embed_and_store_chunks(
                chunks,
                repository_name=(
                    repository_name
                ),
            )
        )

        # -------------------------------------------------
        # Save successful GitHub analysis to SQLite
        # -------------------------------------------------

        if source_type == "github":

            collection_name = (
                sanitize_collection_name(
                    repository_name
                )
            )

            save_repository(
                repository_url=user_input,
                repository_name=(
                    repository_name
                ),
                commit_sha=commit_sha,
                collection_name=(
                    collection_name
                ),
                status="completed",
                chunks_indexed=stored_count,
                index_version=(
                    INDEX_SCHEMA_VERSION
                ),
            )

        # -------------------------------------------------
        # Complete
        # -------------------------------------------------

        update_job(
            job_id,
            status="completed",
            progress=100,
            message="Project ready",
            source_type=source_type,
            repository_name=(
                repository_name
            ),
            chunks_indexed=stored_count,
            cached=False,
        )

    except Exception as error:

        update_job(
            job_id,
            status="failed",
            progress=100,
            message=(
                "Project analysis failed."
            ),
            error=str(error),
        )

    finally:
        if source_type == "github" and repo_path is not None:
            # Only delete temporary folders created by this request.
            resolved = repo_path.resolve()
            if resolved.parent == CLONED_REPOS_DIR.resolve() and resolved.name.startswith("analysis_"):
                shutil.rmtree(resolved, ignore_errors=True)


# Embedded Qdrant and collection replacement require serialized indexing.
_analysis_lock = Lock()

def run_repository_analysis(job_id: str, user_input: str):
    with _analysis_lock:
        _run_repository_analysis(job_id, user_input)


@router.post("/index")
def index_repository(
    request: IndexRequest,
    background_tasks: BackgroundTasks,
):
    """
    Starts repository analysis in the background
    and immediately returns a job ID.
    """

    user_input = request.repo_path.strip()

    if not user_input:
        raise HTTPException(
            status_code=400,
            detail=(
                "Please provide a repository "
                "path or GitHub URL."
            ),
        )

    if is_github_url(user_input):
        try:
            repository_name_from_url(user_input)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
    elif os.getenv("ALLOW_LOCAL_REPOSITORIES", "false").lower() != "true":
        raise HTTPException(status_code=400, detail="Use a public GitHub repository URL. Local paths are disabled.")

    job_id = str(
        uuid.uuid4()
    )

    analysis_jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "message": (
            "Project analysis queued."
        ),
        "source_type": None,
        "repository_name": None,
        "chunks_found": 0,
        "chunks_indexed": 0,
        "cached": False,
        "error": None,
    }

    background_tasks.add_task(
        run_repository_analysis,
        job_id,
        user_input,
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "message": (
            "Project analysis started."
        ),
    }


@router.get(
    "/index/status/{job_id}"
)
def get_index_status(
    job_id: str,
):
    """
    Returns the current repository-analysis status.
    """

    job = analysis_jobs.get(
        job_id
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Analysis job was not found."
            ),
        )

    return job