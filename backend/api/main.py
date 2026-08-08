from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from backend.rag.pipeline import answer_question
from backend.api.indexing_routes import router as indexing_router

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
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# UPDATED REQUEST MODEL
# -----------------------------
class QuestionRequest(BaseModel):
    question: str
    explanation_mode: str = "beginner"


@app.get("/")
def root():
    return {
        "message": "AI Code Review Agent API is running"
    }


@app.post("/ask")
def ask_codebase(request: QuestionRequest):
    answer = answer_question(
        request.question,
        request.explanation_mode,
    )

    return {
        "question": request.question,
        "answer": answer,
    }