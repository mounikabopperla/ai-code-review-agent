"""
Splits a repository into meaningful code and documentation chunks
for embedding and retrieval.
"""

import argparse
import ast
import json
import logging
from pathlib import Path


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("code-chunker")


EXCLUDED_DIRS = {
    "venv",
    "__pycache__",
    ".git",
    "node_modules",
    ".pytest_cache",
    "data",
}


def should_skip_path(path: Path) -> bool:
    """
    Returns True when the path is inside a folder
    that should not be indexed.
    """

    return any(
        excluded in path.parts
        for excluded in EXCLUDED_DIRS
    )


def find_python_files(repo_path: Path) -> list[Path]:
    """
    Find Python files while skipping dependency
    and generated folders.
    """

    py_files = []

    for path in repo_path.rglob("*.py"):
        if should_skip_path(path):
            continue

        py_files.append(path)

    return py_files


def find_document_files(repo_path: Path) -> list[Path]:
    """
    Find README and Markdown documentation files.
    """

    document_files = []

    for path in repo_path.rglob("*.md"):
        if should_skip_path(path):
            continue

        relative_path = path.relative_to(repo_path)

        is_readme = path.name.lower().startswith("readme")

        is_docs_file = (
            len(relative_path.parts) > 1
            and relative_path.parts[0].lower() == "docs"
        )

        if is_readme or is_docs_file:
            document_files.append(path)

    return document_files


def extract_chunks_from_file(
    file_path: Path,
    repo_root: Path,
) -> list[dict]:
    """
    Parse one Python file into meaningful
    function/class chunks.
    """

    try:
        source = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as error:
        logger.warning(
            f"Skipping unreadable file {file_path}: {error}"
        )
        return []

    try:
        tree = ast.parse(
            source,
            filename=str(file_path),
        )
    except SyntaxError as error:
        logger.warning(
            f"Skipping file with syntax error {file_path}: {error}"
        )
        return []

    source_lines = source.splitlines()
    relative_path = str(file_path.relative_to(repo_root))

    chunks = []

    for node in ast.walk(tree):
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        ):
            start_line = node.lineno
            end_line = getattr(
                node,
                "end_lineno",
                start_line,
            )

            chunk_source = "\n".join(
                source_lines[start_line - 1:end_line]
            )

            docstring = ast.get_docstring(node) or ""

            chunk_type = (
                "class"
                if isinstance(node, ast.ClassDef)
                else "function"
            )

            chunks.append(
                {
                    "chunk_id": f"{relative_path}::{node.name}",
                    "file_path": relative_path,
                    "name": node.name,
                    "type": chunk_type,
                    "docstring": docstring,
                    "source_code": chunk_source,
                    "start_line": start_line,
                    "end_line": end_line,
                }
            )

    if not chunks and source.strip():
        chunks.append(
            {
                "chunk_id": f"{relative_path}::_module_level",
                "file_path": relative_path,
                "name": "_module_level",
                "type": "module",
                "docstring": ast.get_docstring(tree) or "",
                "source_code": source,
                "start_line": 1,
                "end_line": len(source_lines),
            }
        )

    return chunks


def extract_document_chunks(
    file_path: Path,
    repo_root: Path,
) -> list[dict]:
    """
    Split a Markdown document into sections based
    on Markdown headings.
    """

    try:
        text = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as error:
        logger.warning(
            f"Skipping unreadable document {file_path}: {error}"
        )
        return []

    lines = text.splitlines()

    if not lines:
        return []

    relative_path = str(file_path.relative_to(repo_root))

    chunks = []

    current_heading = file_path.name
    current_lines = []
    section_start_line = 1

    def save_current_section(end_line: int):
        nonlocal current_lines

        section_text = "\n".join(current_lines).strip()

        if not section_text:
            return

        section_number = len(chunks) + 1

        chunks.append(
            {
                "chunk_id": (
                    f"{relative_path}::section_{section_number}"
                ),
                "file_path": relative_path,
                "name": current_heading,
                "type": "documentation",
                "docstring": "",
                "source_code": section_text,
                "start_line": section_start_line,
                "end_line": end_line,
            }
        )

    for line_number, line in enumerate(lines, start=1):
        stripped_line = line.strip()

        if stripped_line.startswith("#"):
            if current_lines:
                save_current_section(line_number - 1)

            current_heading = (
                stripped_line.lstrip("#").strip()
                or file_path.name
            )

            current_lines = [line]
            section_start_line = line_number

        else:
            current_lines.append(line)

    if current_lines:
        save_current_section(len(lines))

    return chunks


def chunk_repository(repo_path: str) -> list[dict]:
    """
    Chunk supported Python files and documentation
    files in a repository.
    """

    repo_path = Path(repo_path).resolve()

    python_files = find_python_files(repo_path)
    document_files = find_document_files(repo_path)

    logger.info(
        f"Found {len(python_files)} Python files"
    )

    logger.info(
        f"Found {len(document_files)} documentation files"
    )

    all_chunks = []

    for file_path in python_files:
        file_chunks = extract_chunks_from_file(
            file_path,
            repo_path,
        )

        all_chunks.extend(file_chunks)

    for file_path in document_files:
        document_chunks = extract_document_chunks(
            file_path,
            repo_path,
        )

        all_chunks.extend(document_chunks)

    logger.info(
        f"Extracted {len(all_chunks)} chunks total"
    )

    return all_chunks


def save_chunks(
    chunks: list[dict],
    output_path: str,
):
    """
    Save chunks as JSON Lines.
    """

    with open(
        output_path,
        "w",
        encoding="utf-8",
    ) as file:
        for chunk in chunks:
            file.write(
                json.dumps(chunk) + "\n"
            )

    logger.info(
        f"Saved {len(chunks)} chunks -> {output_path}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Chunk a repository into code and "
            "documentation pieces."
        )
    )

    parser.add_argument(
        "--repo-path",
        required=True,
        help="Path to the repository to index.",
    )

    parser.add_argument(
        "--output",
        default="chunks.jsonl",
        help="Where to save the chunks.",
    )

    args = parser.parse_args()

    chunks = chunk_repository(
        args.repo_path
    )

    save_chunks(
        chunks,
        args.output,
    )