import json
import logging
from typing import Literal
from fastapi.responses import StreamingResponse

from pathlib import Path

from fastapi import FastAPI, HTTPException

from pydantic import BaseModel, Field

from fastapi.middleware.cors import CORSMiddleware

from backend.rag.pipeline import (
    answer_question,
    stream_answer_question,
    stream_project_overview,
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
        "https://ai-code-review-agent-1-7tzq.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=8000)
    explanation_mode: Literal["beginner", "intermediate", "expert"] = "beginner"
    repo_path: str


class ProjectOverviewRequest(BaseModel):
    explanation_mode: Literal["beginner", "intermediate", "expert"] = "beginner"
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
    try:
        collection_name = resolve_collection_name(request.repo_path)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

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
    try:
        collection_name = resolve_collection_name(request.repo_path)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    overview = generate_project_overview(
        request.explanation_mode,
        collection_name,
    )

    return {"explanation_mode": request.explanation_mode, "overview": overview}


def stream_response(chunks):
    def events():
        try:
            for text in chunks:
                if text:
                    yield "data: " + json.dumps({"type": "delta", "text": text}) + "\n\n"
            yield 'data: {"type":"done"}\n\n'
        except Exception:
            logging.getLogger(__name__).warning("Answer stream failed")
            yield 'data: {"type":"error","message":"The answer could not be completed. Please retry; the AI service may be busy."}\n\n'
    return StreamingResponse(events(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })


@app.post("/ask/stream")
def ask_stream(request: QuestionRequest):
    try:
        collection = resolve_collection_name(request.repo_path)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return stream_response(stream_answer_question(request.question, request.explanation_mode, collection))


@app.post("/project/overview/stream")
def overview_stream(request: ProjectOverviewRequest):
    try:
        collection = resolve_collection_name(request.repo_path)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return stream_response(stream_project_overview(request.explanation_mode, collection))
