from pathlib import Path

from fastapi import FastAPI

from pydantic import BaseModel

from fastapi.middleware.cors import CORSMiddleware

from backend.rag.pipeline import (
    answer_question,
    generate_project_overview,
)

from backend.api.indexing_routes import (
    router as indexing_router,
    is_github_url,
    repository_name_from_url,
    repository_name_from_path,
)

from backend.vector_store.qdrant_store import (
    sanitize_collection_name,
)


app = FastAPI(
    title="AI Code Review Agent API",
    version="1.0.0",
)


app.include_router(indexing_router)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "https://ai-code-review-agent-omega.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str
    explanation_mode: str = "beginner"
    repo_path: str


class ProjectOverviewRequest(BaseModel):
    explanation_mode: str = "beginner"
    repo_path: str


def resolve_collection_name(
    repo_path: str,
) -> str:
    """
    Converts the selected repository input into
    the corresponding Qdrant collection name.
    """

    user_input = repo_path.strip()

    if not user_input:
        raise ValueError(
            "Repository path or GitHub URL is required."
        )

    if is_github_url(user_input):
        repository_name = (
            repository_name_from_url(
                user_input
            )
        )
    else:
        repository_path = (
            Path(user_input)
            .expanduser()
            .resolve()
        )

        repository_name = (
            repository_name_from_path(
                repository_path
            )
        )

    return sanitize_collection_name(
        repository_name
    )


@app.get("/")
def root():
    return {
        "message": "AI Code Review Agent API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


@app.post("/ask")
def ask_codebase(
    request: QuestionRequest,
):
    collection_name = resolve_collection_name(
        request.repo_path
    )

    answer = answer_question(
        request.question,
        request.explanation_mode,
        collection_name,
    )

    return {
        "question": request.question,
        "answer": answer,
    }


@app.post("/project/overview")
def project_overview(
    request: ProjectOverviewRequest,
):
    collection_name = resolve_collection_name(
        request.repo_path
    )

    overview = generate_project_overview(
        request.explanation_mode,
        collection_name,
    )
