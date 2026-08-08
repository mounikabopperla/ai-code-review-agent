"""
ingestion/chunk_code.py
------------------------
Splits a Python codebase into meaningful chunks for embedding and
retrieval -- one chunk per function or class, not arbitrary line counts.

Why this matters: naive chunking (e.g. "every 50 lines") frequently cuts
a function in half, which destroys retrieval quality -- you'd retrieve
half a function with no context. Using Python's own `ast` (Abstract
Syntax Tree) module means we parse the code the same way Python itself
does, so every chunk is a complete, meaningful unit: one whole function,
one whole class, with its docstring and source code intact.

This module has NO external dependencies beyond Python's standard
library, so it's fully testable without any network access or API keys
-- unlike the embedding step (Phase 2), which needs a real model.

Usage:
    python chunk_code.py --repo-path /path/to/repo --output chunks.jsonl
"""

import argparse
import ast
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("code-chunker")

# Folders we never want to index -- generated files, dependencies, caches
EXCLUDED_DIRS = {"venv", "__pycache__", ".git", "node_modules", ".pytest_cache", "data"}


def find_python_files(repo_path: Path) -> list[Path]:
    """Walks the repo and returns every .py file, skipping excluded folders."""
    py_files = []
    for path in repo_path.rglob("*.py"):
        if any(excluded in path.parts for excluded in EXCLUDED_DIRS):
            continue
        py_files.append(path)
    return py_files


def extract_chunks_from_file(file_path: Path, repo_root: Path) -> list[dict]:
    """
    Parses one Python file and returns one chunk per top-level function
    and class definition. If the file fails to parse (e.g. a syntax
    error, or a non-UTF8 file), it's skipped and logged -- not crashed on,
    since a single bad file shouldn't stop indexing the whole repo.
    """
    try:
        source = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        logger.warning(f"Skipping unreadable file {file_path}: {e}")
        return []

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as e:
        logger.warning(f"Skipping file with syntax error {file_path}: {e}")
        return []

    source_lines = source.splitlines()
    relative_path = str(file_path.relative_to(repo_root))
    chunks = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # Only take TOP-LEVEL definitions (direct children of the module),
            # not every nested function -- otherwise we'd double-count methods
            # inside classes as both part of the class chunk AND their own chunk.
            if node not in ast.iter_child_nodes(tree):
                continue

            start_line = node.lineno
            end_line = getattr(node, "end_lineno", start_line)
            chunk_source = "\n".join(source_lines[start_line - 1:end_line])

            docstring = ast.get_docstring(node) or ""
            chunk_type = "class" if isinstance(node, ast.ClassDef) else "function"

            chunks.append({
                "chunk_id": f"{relative_path}::{node.name}",
                "file_path": relative_path,
                "name": node.name,
                "type": chunk_type,
                "docstring": docstring,
                "source_code": chunk_source,
                "start_line": start_line,
                "end_line": end_line,
            })

    # If a file has no top-level functions/classes (e.g. a pure script or
    # config file), still index the whole file as one chunk, so it's not
    # silently invisible to search.
    if not chunks and source.strip():
        chunks.append({
            "chunk_id": f"{relative_path}::_module_level",
            "file_path": relative_path,
            "name": "_module_level",
            "type": "module",
            "docstring": ast.get_docstring(tree) or "",
            "source_code": source,
            "start_line": 1,
            "end_line": len(source_lines),
        })

    return chunks


def chunk_repository(repo_path: str) -> list[dict]:
    repo_path = Path(repo_path).resolve()
    py_files = find_python_files(repo_path)
    logger.info(f"Found {len(py_files)} Python files to chunk in {repo_path}")

    all_chunks = []
    for file_path in py_files:
        file_chunks = extract_chunks_from_file(file_path, repo_path)
        all_chunks.extend(file_chunks)

    logger.info(f"Extracted {len(all_chunks)} chunks total")
    return all_chunks


def save_chunks(chunks: list[dict], output_path: str):
    with open(output_path, "w") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk) + "\n")
    logger.info(f"Saved {len(chunks)} chunks -> {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chunk a Python repo into function/class-level pieces")
    parser.add_argument("--repo-path", required=True, help="Path to the repo to index")
    parser.add_argument("--output", default="chunks.jsonl", help="Where to save the chunks")
    args = parser.parse_args()

    chunks = chunk_repository(args.repo_path)
    save_chunks(chunks, args.output)
