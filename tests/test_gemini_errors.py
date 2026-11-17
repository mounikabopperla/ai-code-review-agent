"""
Tests for the safe Gemini error messages in
backend/llm/generator.py.

These tests use fake errors only. No API key, no real
Gemini call, and no secret is ever asserted or printed.
"""

import os

os.environ.setdefault("GOOGLE_API_KEY", "test-google-key")
os.environ.setdefault("GEMINI_MODEL", "gemini-test-model")

from backend.llm.generator import _gemini_error_message


class FakeError(Exception):
    def __init__(self, code, message=""):
        super().__init__(message)
        self.code = code


def test_auth_error_points_to_render_key():
    message = _gemini_error_message(FakeError(401, "unauthenticated"))
    assert "GOOGLE_API_KEY" in message
    assert "test-google-key" not in message


def test_model_not_found_points_to_render_model():
    message = _gemini_error_message(FakeError(404, "model not found"))
    assert "GEMINI_MODEL" in message
    assert "gemini-2.5-flash" in message


def test_quota_error_is_named():
    message = _gemini_error_message(FakeError(429, "quota exceeded"))
    assert "429" in message


def test_server_error_says_try_again():
    message = _gemini_error_message(FakeError(503, "unavailable"))
    assert "temporarily unavailable" in message
