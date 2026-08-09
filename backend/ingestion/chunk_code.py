"""
Splits a repository into useful code and documentation chunks
for embedding and retrieval.

The production indexer intentionally skips low-value content such as
tests, examples, generated files, virtual environments, and build
artifacts so repository indexing stays fast enough for an interactive
application.
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


# Directories that usually do not help answer questions
# about the main application architecture.
EXCLUDED_DIRS = {
    "venv",
    ".venv",
    "__pycache__",
    ".git",
    "node_modules",
    ".pytest_cache",
    "data",
    "build",
    "dist",
    "coverage",
    ".coverage",
    "tests",
    "test",
    "testing",
    "examples",
    "example",
    "benchmarks",
    "benchmark",
}


# Prevent a very large repository from creating thousands
# of embeddings on a small cloud server.
MAX_TOTAL_CHUNKS = 120

# Keep documentation useful, but prevent documentation-heavy
# repositories from dominating the index.
MAX_DOCUMENT_CHUNKS = 20


def should_skip_path(path: Path) -> bool:
    """
    Returns True when the path is inside a directory
    that should not be indexed.
    """

    lowered_parts = {
        part.lower()
        for part in path.parts
    }

    return any(
        excluded.lower() in lowered_parts
        for excluded in EXCLUDED_DIRS
    )


def find_python_files(
    repo_path: Path,
) -> list[Path]:
    """
    Find production Python files while skipping tests,
    dependencies, examples, and generated folders.
    """

    py_files = []

    for path in repo_path.rglob("*.py"):
        if should_skip_path(path):
            continue

        py_files.append(path)

    # Keep indexing deterministic.
    return sorted(py_files)


def find_document_files(
    repo_path: Path,
) -> list[Path]:
    """
    Find useful README and Markdown documentation.

    README files are strongly preferred because they normally
    contain the best repository-level explanation.
    """

    document_files = []

    for path in repo_path.rglob("*.md"):
        if should_skip_path(path):
            continue

        relative_path = path.relative_to(
            repo_path
        )

        is_readme = (
            path.name.lower()
            .startswith("readme")
        )

        is_docs_file = (
            len(relative_path.parts) > 1
            and relative_path.parts[0].lower()
            == "docs"
        )

        if is_readme or is_docs_file:
            document_files.append(path)

    # README first, then remaining documentation.
    return sorted(
        document_files,
        key=lambda path: (
            0
            if path.name.lower().startswith(
                "readme"
            )
            else 1,
            str(path),
        ),
    )


def extract_chunks_from_file(
    file_path: Path,
    repo_root: Path,
) -> list[dict]:
    """
    Parse one Python file into function/class chunks.
    """

    try:
        source = file_path.read_text(
            encoding="utf-8"
        )

    except (
        UnicodeDecodeError,
        OSError,
    ) as error:
        logger.warning(
            f"Skipping unreadable file "
            f"{file_path}: {error}"
        )
        return []

    try:
        tree = ast.parse(
            source,
            filename=str(file_path),
        )

    except SyntaxError as error:
        logger.warning(
            f"Skipping file with syntax error "
            f"{file_path}: {error}"
        )
        return []

    source_lines = source.splitlines()

    relative_path = str(
        file_path.relative_to(
            repo_root
        )
    )

    chunks = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        ):
            continue

        start_line = node.lineno

        end_line = getattr(
            node,
            "end_lineno",
            start_line,
        )

        chunk_source = "\n".join(
            source_lines[
                start_line - 1:end_line
            ]
        )

        docstring = (
            ast.get_docstring(node)
            or ""
        )

        chunk_type = (
            "class"
            if isinstance(
                node,
                ast.ClassDef,
            )
            else "function"
        )

        chunks.append(
            {
                "chunk_id": (
                    f"{relative_path}"
                    f"::{node.name}"
                ),
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
                "chunk_id": (
                    f"{relative_path}"
                    "::_module_level"
                ),
                "file_path": relative_path,
                "name": "_module_level",
                "type": "module",
                "docstring": (
                    ast.get_docstring(tree)
                    or ""
                ),
                "source_code": source,
                "start_line": 1,
                "end_line": len(
                    source_lines
                ),
            }
        )

    return chunks


def extract_document_chunks(
    file_path: Path,
    repo_root: Path,
) -> list[dict]:
    """
    Split Markdown documentation into sections
    based on headings.
    """

    try:
        text = file_path.read_text(
            encoding="utf-8"
        )

    except (
        UnicodeDecodeError,
        OSError,
    ) as error:
        logger.warning(
            f"Skipping unreadable document "
            f"{file_path}: {error}"
        )
        return []

    lines = text.splitlines()

    if not lines:
        return []

    relative_path = str(
        file_path.relative_to(
            repo_root
        )
    )

    chunks = []

    current_heading = file_path.name
    current_lines = []
    section_start_line = 1

    def save_current_section(
        end_line: int,
    ):
        nonlocal current_lines

        section_text = "\n".join(
            current_lines
        ).strip()

        if not section_text:
            return

        section_number = (
            len(chunks) + 1
        )

        chunks.append(
            {
                "chunk_id": (
                    f"{relative_path}"
                    f"::section_"
                    f"{section_number}"
                ),
                "file_path": relative_path,
                "name": current_heading,
                "type": "documentation",
                "docstring": "",
                "source_code": (
                    section_text
                ),
                "start_line": (
                    section_start_line
                ),
                "end_line": end_line,
            }
        )

    for (
        line_number,
        line,
    ) in enumerate(
        lines,
        start=1,
    ):
        stripped_line = (
            line.strip()
        )

        if stripped_line.startswith(
            "#"
        ):
            if current_lines:
                save_current_section(
                    line_number - 1
                )

            current_heading = (
                stripped_line
                .lstrip("#")
                .strip()
                or file_path.name
            )

            current_lines = [
                line
            ]

            section_start_line = (
                line_number
            )

        else:
            current_lines.append(
                line
            )

    if current_lines:
        save_current_section(
            len(lines)
        )

    return chunks


def chunk_repository(
    repo_path: str,
) -> list[dict]:
    """
    Chunk useful production Python code and
    selected documentation.

    Very large repositories are capped so indexing
    remains practical on limited cloud compute.
    """

    repo_path = Path(
        repo_path
    ).resolve()

    python_files = find_python_files(
        repo_path
    )

    document_files = (
        find_document_files(
            repo_path
        )
    )

    logger.info(
        f"Found "
        f"{len(python_files)} "
        f"production Python files"
    )

    logger.info(
        f"Found "
        f"{len(document_files)} "
        f"documentation files"
    )

    documentation_chunks = []

    # Documentation first so README/project-level
    # context is guaranteed to survive the total cap.
    for file_path in document_files:
        file_chunks = (
            extract_document_chunks(
                file_path,
                repo_path,
            )
        )

        documentation_chunks.extend(
            file_chunks
        )

        if (
            len(
                documentation_chunks
            )
            >= MAX_DOCUMENT_CHUNKS
        ):
            documentation_chunks = (
                documentation_chunks[
                    :MAX_DOCUMENT_CHUNKS
                ]
            )
            break

    code_chunks = []

    available_code_slots = (
        MAX_TOTAL_CHUNKS
        - len(
            documentation_chunks
        )
    )

    for file_path in python_files:
        file_chunks = (
            extract_chunks_from_file(
                file_path,
                repo_path,
            )
        )

        code_chunks.extend(
            file_chunks
        )

        if (
            len(code_chunks)
            >= available_code_slots
        ):
            code_chunks = (
                code_chunks[
                    :available_code_slots
                ]
            )
            break

    all_chunks = (
        documentation_chunks
        + code_chunks
    )

    logger.info(
        f"Documentation chunks: "
        f"{len(documentation_chunks)}"
    )

    logger.info(
        f"Code chunks: "
        f"{len(code_chunks)}"
    )

    logger.info(
        f"Extracted "
        f"{len(all_chunks)} "
        f"chunks total"
    )

    if (
        len(all_chunks)
        >= MAX_TOTAL_CHUNKS
    ):
        logger.info(
            "Repository reached the "
            f"{MAX_TOTAL_CHUNKS}-chunk "
            "production indexing limit."
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
                json.dumps(chunk)
                + "\n"
            )

    logger.info(
        f"Saved "
        f"{len(chunks)} chunks "
        f"-> {output_path}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Chunk a repository into "
            "useful code and "
            "documentation pieces."
        )
    )

    parser.add_argument(
        "--repo-path",
        required=True,
        help=(
            "Path to the repository "
            "to index."
        ),
    )

    parser.add_argument(
        "--output",
        default="chunks.jsonl",
        help=(
            "Where to save "
            "the chunks."
        ),
    )

    args = parser.parse_args()

    chunks = chunk_repository(
        args.repo_path
    )

    save_chunks(
        chunks,
        args.output,
    )