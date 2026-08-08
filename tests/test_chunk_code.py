"""
tests/test_chunk_code.py
--------------------------
Tests the AST-based code chunker using real temporary Python files.

Run with:  pytest tests/test_chunk_code.py -v
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.chunk_code import chunk_repository


def write_file(tmp_path, relative_path, content):
    file_path = tmp_path / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)
    return file_path


def test_extracts_one_chunk_per_function(tmp_path):
    write_file(tmp_path, "sample.py", '''
def add(a, b):
    """Adds two numbers."""
    return a + b

def subtract(a, b):
    """Subtracts b from a."""
    return a - b
''')
    chunks = chunk_repository(str(tmp_path))
    names = {c["name"] for c in chunks}
    assert names == {"add", "subtract"}
    assert all(c["type"] == "function" for c in chunks)


def test_extracts_class_as_one_chunk_not_split_by_methods(tmp_path):
    write_file(tmp_path, "sample.py", '''
class Calculator:
    """A simple calculator."""

    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b
''')
    chunks = chunk_repository(str(tmp_path))
    assert len(chunks) == 1
    assert chunks[0]["type"] == "class"
    assert chunks[0]["name"] == "Calculator"
    assert "def add" in chunks[0]["source_code"]
    assert "def subtract" in chunks[0]["source_code"]


def test_docstring_is_captured(tmp_path):
    write_file(tmp_path, "sample.py", '''
def greet(name):
    """Returns a greeting message."""
    return f"Hello, {name}"
''')
    chunks = chunk_repository(str(tmp_path))
    assert chunks[0]["docstring"] == "Returns a greeting message."


def test_file_with_no_functions_becomes_one_module_chunk(tmp_path):
    write_file(tmp_path, "config.py", '''
DEBUG = True
MAX_RETRIES = 3
''')
    chunks = chunk_repository(str(tmp_path))
    assert len(chunks) == 1
    assert chunks[0]["type"] == "module"


def test_file_with_syntax_error_is_skipped_not_crashed(tmp_path):
    write_file(tmp_path, "broken.py", "def broken(:\n    this is not valid python")
    write_file(tmp_path, "good.py", "def works():\n    return True")

    chunks = chunk_repository(str(tmp_path))
    names = {c["name"] for c in chunks}
    assert "works" in names
    assert "broken" not in names


def test_excluded_directories_are_skipped(tmp_path):
    write_file(tmp_path, "real_code.py", "def real():\n    pass")
    write_file(tmp_path, "venv/lib/some_dependency.py", "def vendored():\n    pass")
    write_file(tmp_path, "__pycache__/cached.py", "def cached():\n    pass")

    chunks = chunk_repository(str(tmp_path))
    names = {c["name"] for c in chunks}
    assert "real" in names
    assert "vendored" not in names
    assert "cached" not in names


def test_chunk_id_includes_file_path_and_name(tmp_path):
    write_file(tmp_path, "utils/helpers.py", "def helper_fn():\n    pass")
    chunks = chunk_repository(str(tmp_path))
    assert chunks[0]["chunk_id"] == "utils/helpers.py::helper_fn"


def test_multiple_files_all_get_chunked(tmp_path):
    write_file(tmp_path, "a.py", "def fn_a():\n    pass")
    write_file(tmp_path, "b.py", "def fn_b():\n    pass")
    write_file(tmp_path, "sub/c.py", "def fn_c():\n    pass")

    chunks = chunk_repository(str(tmp_path))
    names = {c["name"] for c in chunks}
    assert names == {"fn_a", "fn_b", "fn_c"}


def test_async_function_is_captured(tmp_path):
    write_file(tmp_path, "async_sample.py", '''
async def fetch_data():
    """Fetches data asynchronously."""
    pass
''')
    chunks = chunk_repository(str(tmp_path))
    assert len(chunks) == 1
    assert chunks[0]["name"] == "fetch_data"
