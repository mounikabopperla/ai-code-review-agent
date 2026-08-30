from pathlib import Path

import shutil
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


def repository_name_from_url(
    url: str,
) -> str:
    """
    Extracts repository name from a GitHub URL.
    """

    repo_name = (
        url.rstrip("/")
        .split("/")[-1]
    )

    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    return repo_name


def repository_name_from_path(
    repo_path: Path,
) -> str:
    """
    Uses the local directory name as
    the repository name.
    """

    return repo_path.name


def clone_github_repository(
    url: str,
) -> Path:
    """
    Clones a public GitHub repository locally.
    """

    CLONED_REPOS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    repo_name = repository_name_from_url(
        url
    )

    if not repo_name:
        raise ValueError(
            "Could not determine repository "
            "name from GitHub URL."
        )

    destination = (
        CLONED_REPOS_DIR
        / repo_name
    ).resolve()

    if destination.exists():
        shutil.rmtree(
            destination
        )

    try:
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                url,
                str(destination),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    except FileNotFoundError as error:
        raise RuntimeError(
            "Git is not installed or "
            "could not be found."
        ) from error

    except subprocess.CalledProcessError as error:
        message = (
            error.stderr.strip()
            or error.stdout.strip()
            or "Git clone failed."
        )

        raise RuntimeError(
            "Could not read this GitHub project: "
            f"{message}"
        ) from error

    return destination


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


def run_repository_analysis(
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