from backend.retrieval.search import search_vectors

from backend.llm.generator import (
    ask_gemini,
    build_grounded_prompt,
)


def build_sources(
    retrieved_chunks: list[dict],
) -> str:
    """
    Builds a readable source list from retrieved chunks.
    """

    if not retrieved_chunks:
        return ""

    source_lines = []
    seen = set()

    for chunk in retrieved_chunks:
        file_path = chunk.get(
            "file_path",
            "Unknown file",
        )

        name = chunk.get(
            "name",
            "",
        )

        start_line = chunk.get(
            "start_line"
        )

        end_line = chunk.get(
            "end_line"
        )

        source_key = (
            file_path,
            name,
            start_line,
            end_line,
        )

        if source_key in seen:
            continue

        seen.add(source_key)

        source_lines.append(
            f"- **{file_path}**"
        )

        if name and name not in {
            "_module_level",
            file_path,
        }:
            source_lines.append(
                f"  - Section / Function: `{name}`"
            )

        if (
            start_line is not None
            and end_line is not None
        ):
            source_lines.append(
                f"  - Lines: "
                f"{start_line}-{end_line}"
            )

    if not source_lines:
        return ""

    return (
        "\n\n---\n\n"
        "### Sources\n\n"
        + "\n".join(source_lines)
    )


def answer_question(
    question: str,
    explanation_mode: str = "beginner",
    collection_name: str | None = None,
) -> str:
    """
    Complete Retrieval-Augmented Generation
    pipeline for normal user questions.

    The collection_name identifies the repository
    that the user selected.
    """

    results = search_vectors(
        question=question,
        limit=5,
        collection_name=collection_name,
    )

    retrieved_chunks = [
        result.payload or {}
        for result in results
    ]

    prompt = build_grounded_prompt(
        question,
        retrieved_chunks,
        explanation_mode,
    )

    answer = ask_gemini(
        prompt
    )

    sources = build_sources(
        retrieved_chunks,
    )

    return answer + sources


def _chunk_identity(
    chunk: dict,
) -> tuple:
    """
    Creates a stable identity for a retrieved chunk
    so duplicate results can be removed.
    """

    return (
        chunk.get("file_path"),
        chunk.get("name"),
        chunk.get("start_line"),
        chunk.get("end_line"),
    )


def retrieve_overview_chunks(
    collection_name: str | None = None,
) -> list[dict]:
    """
    Retrieves broad repository context for a project
    overview.

    Several focused searches are performed and their
    results are combined.
    """

    overview_queries = [
        (
            "What is this project and what problem "
            "does it solve?"
        ),
        (
            "What are the main components, modules, "
            "and architecture of this project?"
        ),
        (
            "Where does this application start and "
            "what are its main entry points?"
        ),
        (
            "How do the important components work "
            "together and what is the main data flow?"
        ),
        (
            "What technologies, dependencies, and "
            "frameworks are important in this project?"
        ),
    ]

    retrieved_chunks = []
    seen_chunks = set()

    for query in overview_queries:
        results = search_vectors(
            question=query,
            limit=4,
            collection_name=collection_name,
        )

        for result in results:
            chunk = (
                result.payload
                or {}
            )

            identity = _chunk_identity(
                chunk
            )

            if identity in seen_chunks:
                continue

            seen_chunks.add(
                identity
            )

            retrieved_chunks.append(
                chunk
            )

    return retrieved_chunks


def generate_project_overview(
    explanation_mode: str = "beginner",
    collection_name: str | None = None,
) -> str:
    """
    Generates a structured high-level overview of
    the selected repository.
    """

    retrieved_chunks = (
        retrieve_overview_chunks(
            collection_name
        )
    )

    if not retrieved_chunks:
        return (
            "I could not find enough indexed project "
            "content to generate an overview."
        )

    overview_request = """
Give me a structured overview of this project.

Explain:

1. What this project does.

2. What problem it is designed to solve.

3. The main technologies or libraries used.

4. The most important files, modules, or components.

5. The likely application entry point, if it can be
   determined from the retrieved code.

6. How the major components work together.

7. The typical execution or data flow through the
   project.

8. What someone new to this project should understand
   first.

Keep the overview grounded only in the retrieved
repository context.

Do not invent architecture, technologies, entry
points, or behavior that cannot be supported by the
retrieved code.

If something cannot be determined confidently from
the available context, say so clearly.
""".strip()

    prompt = build_grounded_prompt(
        overview_request,
        retrieved_chunks,
        explanation_mode,
    )

    answer = ask_gemini(
        prompt
    )

    sources = build_sources(
        retrieved_chunks,
    )

    return answer + sources


if __name__ == "__main__":
    question = input(
        "Ask about the codebase:\n> "
    )

    explanation_mode = input(
        "Explanation mode "
        "(beginner/intermediate/expert) "
        "[beginner]:\n> "
    ).strip()

    if not explanation_mode:
        explanation_mode = "beginner"

    answer = answer_question(
        question,
        explanation_mode,
    )

    print("\n")
    print(answer)