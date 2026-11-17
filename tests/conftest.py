"""Tests never read .env or initialize an authenticated model client."""
import os
import tempfile
from pathlib import Path

os.environ["LOAD_DOTENV"] = "false"
os.environ["GOOGLE_API_KEY"] = "test-only-not-a-real-key"
os.environ["GEMINI_MODEL"] = "test-only-model"
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("QDRANT_URL", None)
os.environ.pop("QDRANT_API_KEY", None)
_test_storage = tempfile.TemporaryDirectory(prefix="code_review_tests_")
os.environ["REPOSITORY_CACHE_PATH"] = str(Path(_test_storage.name) / "repositories.db")
os.environ["ANSWER_CACHE_PATH"] = str(Path(_test_storage.name) / "answers.db")
