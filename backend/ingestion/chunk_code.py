"""
Splits a repository into useful code and documentation chunks
for retrieval.

The indexer prioritizes important production source files so
critical application logic is not accidentally excluded simply
because files happen to be alphabetically later in the repository.

Tests, examples, generated files, dependencies, and build
artifacts are skipped.
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


# Directories that usually do not help answer questions about
# the main application architecture.
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


# Maximum number of chunks stored for one repository.
#
# This keeps indexing practical for deployment while the
# priority system below makes the limited slots more useful.
MAX_TOTAL_CHUNKS = 120


# Maximum documentation chunks.
MAX_DOCUMENT_CHUNKS = 20


# Important source files are processed first.
#
# These names are intentionally generic enough to work across
# many Python repositories.
IMPORTANT_FILE_NAMES = {
    "main.py": 100,
    "app.py": 95,
    "application.py": 95,
    "core.py": 95,
    "server.py": 90,
    "api.py": 90,
    "router.py": 90,
    "routes.py": 90,
    "pipeline.py": 85,
    "service.py": 80,
    "services.py": 80,
    "parser.py": 80,
    "engine.py": 80,
    "manager.py": 75,
    "models.py": 75,
    "types.py": 75,
    "utils.py": 70,
    "decorators.py": 70,
    "config.py": 65,
    "__init__.py": 60,
}


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


def file_priority(path: Path) -> tuple:
    """
    Returns a deterministic priority for a source file.

    Important application files are processed first.
    Files inside src/ are preferred over less central locations.
    """

    name = path.name.lower()

    priority = IMPORTANT_FILE_NAMES.get(
        name,
        10,
    )

    relative_parts = [
        part.lower()
        for part in path.parts
    ]

    src_bonus = (
        20
        if "src" in relative_parts
        else 0
    )

    package_bonus = (
        10
        if len(relative_parts) >= 2
        and relative_parts[-2] not in {
            "",
            ".",
        }
        else 0
    )

    return (
        priority + src_bonus,
        str(path).lower(),
    )


def find_python_files(
    repo_path: Path,
) -> list[Path]:
    """
    Find production Python files while skipping
    tests, dependencies, examples, and generated folders.

    Files are ordered by architectural importance rather
    than simple alphabetical order.
    """

    py_files = []

    for path in repo_path.rglob("*.py"):
        if should_skip_path(path):
            continue

        py_files.append(path)

    return sorted(
        py_files,
        key=file_priority,
        reverse=True,
    )


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
            path.name.lower().startswith(
                "readme"
            )
        )

        is_docs_file = (
            len(relative_path.parts) > 1
            and relative_path.parts[0].lower()
            == "docs"
        )

        if is_readme or is_docs_file:
            document_files.append(path)

    return sorted(
        document_files,
        key=lambda path: (
            0
            if path.name.lower().startswith(
                "readme"
            )
            else 1,
            str(path).lower(),
        ),
    )


def extract_chunks_from_file(
    file_path: Path,
    repo_root: Path,
) -> list[dict]:
    """
    Parse one Python file into function/class chunks.

    A module-level fallback is created when the file does not
    contain classes or functions.
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

    # Sort AST nodes by source location so chunks are
    # deterministic and follow the file naturally.
    nodes = [
        node
        for node in ast.walk(tree)
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        )
    ]

    nodes.sort(
        key=lambda node: (
            node.lineno,
            getattr(
                node,
                "end_lineno",
                node.lineno,
            ),
        )
    )

    for node in nodes:
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
                    f"::{start_line}"
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
                "source_code": section_text,
                "start_line": section_start_line,
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
        stripped_line = line.strip()

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

    Important source files are processed first so the
    total chunk limit favors core application logic.
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

    # -----------------------------------------------------
    # Documentation
    # -----------------------------------------------------

    documentation_chunks = []

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
            len(documentation_chunks)
            >= MAX_DOCUMENT_CHUNKS
        ):
            documentation_chunks = (
                documentation_chunks[
                    :MAX_DOCUMENT_CHUNKS
                ]
            )
            break

    # -----------------------------------------------------
    # Code
    # -----------------------------------------------------

    available_code_slots = (
        MAX_TOTAL_CHUNKS
        - len(documentation_chunks)
    )

    code_chunks = []

    for file_path in python_files:
        file_chunks = (
            extract_chunks_from_file(
                file_path,
                repo_path,
            )
        )

        if not file_chunks:
            continue

        remaining_slots = (
            available_code_slots
            - len(code_chunks)
        )

        if remaining_slots <= 0:
            break

        # Important files are processed first.
        # Their chunks therefore receive priority when
        # the repository reaches the production limit.
        code_chunks.extend(
            file_chunks[
                :remaining_slots
            ]
        )

        if (
            len(code_chunks)
            >= available_code_slots
        ):
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
        "repo_path",
        help="Path to the repository",
    )

    parser.add_argument(
        "--output",
        default="chunks.jsonl",
        help="Output JSONL file",
    )

    args = parser.parse_args()

    chunks = chunk_repository(
        args.repo_path
    )

    save_chunks(
        chunks,
        args.output,
    )