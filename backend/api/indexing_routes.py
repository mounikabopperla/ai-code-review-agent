from pathlib import Path
import shutil
import subprocess

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.ingestion.chunk_code import chunk_repository
from backend.embeddings.embed_chunks import embed_and_store_chunks


router = APIRouter()

CLONED_REPOS_DIR = Path("cloned_repos")


class IndexRequest(BaseModel):
    repo_path: str


def is_github_url(value: str) -> bool:
    """
    Returns True when the input looks like a GitHub repository URL.
    """
    value = value.strip().lower()

    return (
        value.startswith("https://github.com/")
        or value.startswith("http://github.com/")
    )


def repository_name_from_url(url: str) -> str:
    """
    Extracts the repository name from a GitHub URL.
    """
    repo_name = url.rstrip("/").split("/")[-1]

    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    return repo_name


def repository_name_from_path(
    repo_path: Path,
) -> str:
    """
    Uses the local folder name as the repository name.
    """
    return repo_path.name


def clone_github_repository(url: str) -> Path:
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
        raise HTTPException(
            status_code=400,
            detail=(
                "Could not determine repository "
                "name from GitHub URL."
            ),
        )

    destination = (
        CLONED_REPOS_DIR / repo_name
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
        raise HTTPException(
            status_code=500,
            detail=(
                "Git is not installed or "
                "could not be found."
            ),
        ) from error

    except subprocess.CalledProcessError as error:
        message = (
            error.stderr.strip()
            or error.stdout.strip()
            or "Git clone failed."
        )

        raise HTTPException(
            status_code=400,
            detail=(
                "Could not clone repository: "
                f"{message}"
            ),
        ) from error

    return destination


@router.post("/index")
def index_repository(
    request: IndexRequest,
):
    """
    Index either:
    - a local repository path
    - or a public GitHub repository URL
    """

    user_input = request.repo_path.strip()

    if not user_input:
        raise HTTPException(
            status_code=400,
            detail=(
                "Repository path or GitHub URL "
                "is required."
            ),
        )

    if is_github_url(
        user_input
    ):
        repo_path = clone_github_repository(
            user_input
        )

        repository_name = repository_name_from_url(
            user_input
        )

        source_type = "github"

    else:
        repo_path = (
            Path(user_input)
            .expanduser()
            .resolve()
        )

        source_type = "local"

        if not repo_path.exists():
            raise HTTPException(
                status_code=404,
                detail=(
                    "Repository path does not exist: "
                    f"{repo_path}"
                ),
            )

        if not repo_path.is_dir():
            raise HTTPException(
                status_code=400,
                detail=(
                    "The provided path is not "
                    "a directory."
                ),
            )

        repository_name = repository_name_from_path(
            repo_path
        )

    try:
        chunks = chunk_repository(
            str(repo_path)
        )

        if not chunks:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No supported Python or Markdown "
                    "content was found."
                ),
            )

        stored_count = embed_and_store_chunks(
            chunks,
            repository_name=repository_name,
        )

        return {
            "status": "success",
            "source_type": source_type,
            "repository_name": repository_name,
            "repository": str(repo_path),
            "chunks_indexed": stored_count,
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Repository indexing failed: "
                f"{str(error)}"
            ),
        ) from error