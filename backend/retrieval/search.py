from backend.embeddings.embed_chunks import generate_embedding

from backend.vector_store.qdrant_store import (
    SPARSE_VECTOR_NAME,
    get_active_collection,
    get_qdrant_client,
)


def detect_query_intent(
    question: str,
) -> str:
    """
    Classifies the user's question into a simple
    retrieval intent.
    """

    question_lower = question.lower()

    project_phrases = [
        "what does this project do",
        "what is this project",
        "what problem does this project solve",
        "what problem does it solve",
        "explain this project",
        "summarize this project",
        "summarize this repository",
        "repository overview",
        "project overview",
        "purpose of this project",
        "why was this project created",
        "how does this project help",
    ]

    code_phrases = [
        "where is",
        "implemented",
        "implementation",
        "function",
        "method",
        "class",
        "defined",
        "source code",
        "show me",
        "which file",
        "how does this function",
        "how does this class",
    ]

    if any(
        phrase in question_lower
        for phrase in project_phrases
    ):
        return "project"

    if any(
        phrase in question_lower
        for phrase in code_phrases
    ):
        return "code"

    return "general"


def retrieval_bonus(
    payload: dict,
    intent: str,
) -> float:
    """
    Applies ranking bonuses depending on query intent.
    """

    chunk_type = str(
        payload.get("type", "")
    ).lower()

    file_path = str(
        payload.get("file_path", "")
    ).lower()

    bonus = 0.0

    if intent == "project":
        if chunk_type == "documentation":
            bonus += 0.30

        if "readme" in file_path:
            bonus += 0.40

        if file_path.startswith("docs/"):
            bonus += 0.15

        if (
            file_path.startswith("tests/")
            or "/tests/" in file_path
        ):
            bonus -= 0.50

    elif intent == "code":
        if chunk_type in {
            "function",
            "class",
            "module",
        }:
            bonus += 0.20

        if chunk_type == "documentation":
            bonus -= 0.05

    return bonus


def search_vectors(
    query_vector=None,
    question: str = "",
    limit: int = 5,
    collection_name: str | None = None,
):
    """
    Searches a repository using local BM25 sparse retrieval.

    If collection_name is provided, that specific Qdrant
    collection is searched.

    If collection_name is not provided, the currently active
    collection is used for backward compatibility.

    This allows the application to support explicit
    repository selection for multi-user deployment.
    """

    client = get_qdrant_client()

    if collection_name is None:
        collection_name = get_active_collection()

    intent = detect_query_intent(
        question
    )

    if query_vector is None:
        query_vector = generate_embedding(
            question
        )

    candidate_limit = max(
        limit * 4,
        20,
    )

    response = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        using=SPARSE_VECTOR_NAME,
        limit=candidate_limit,
        with_payload=True,
    )

    ranked_results = sorted(
        response.points,
        key=lambda result: (
            result.score
            + retrieval_bonus(
                result.payload or {},
                intent,
            )
        ),
        reverse=True,
    )

    return ranked_results[:limit]


if __name__ == "__main__":
    query = "What does this project do?"

    results = search_vectors(
        question=query,
        limit=5,
    )

    print(
        "Intent:",
        detect_query_intent(query),
    )

    print(
        "Collection:",
        get_active_collection(),
    )

    for result in results:
        print()

        print(
            "Score:",
            result.score,
        )

        print(
            "Type:",
            result.payload.get(
                "type"
            ),
        )

        print(
            "File:",
            result.payload.get(
                "file_path"
            ),
        )

        print(
            "Name:",
            result.payload.get(
                "name"
            ),
        )