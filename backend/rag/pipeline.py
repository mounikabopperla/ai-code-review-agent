from backend.embeddings.model import load_embedding_model
from backend.embeddings.embed_chunks import generate_embedding
from backend.retrieval.search import search_vectors
from backend.llm.generator import (
    ask_gemini,
    build_grounded_prompt,
)


tokenizer, model = load_embedding_model()


def build_sources(retrieved_chunks: list[dict]) -> str:
    """
    Builds a readable source list from retrieved chunks.
    """

    if not retrieved_chunks:
        return ""

    source_lines = []
    seen = set()

    for chunk in retrieved_chunks:
        file_path = chunk.get("file_path", "Unknown file")
        name = chunk.get("name", "")
        start_line = chunk.get("start_line")
        end_line = chunk.get("end_line")

        source_key = (
            file_path,
            name,
            start_line,
            end_line,
        )

        if source_key in seen:
            continue

        seen.add(source_key)

        source_lines.append(f"- **{file_path}**")

        if name and name not in {
            "_module_level",
            file_path,
        }:
            source_lines.append(
                f"  - Section / Function: `{name}`"
            )

        if start_line is not None and end_line is not None:
            source_lines.append(
                f"  - Lines: {start_line}-{end_line}"
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
) -> str:
    """
    Complete Retrieval-Augmented Generation pipeline.

    Steps:
    1. Convert the user's question into an embedding.
    2. Retrieve relevant repository chunks.
    3. Build a grounded prompt.
    4. Ask Gemini for the answer.
    5. Attach the retrieved source references.
    """

    query_embedding = generate_embedding(
        question,
        tokenizer,
        model,
    )

    results = search_vectors(
        query_embedding,
        question=question,
        limit=5,
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

    answer = ask_gemini(prompt)

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