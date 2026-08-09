import re

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams


QDRANT_PATH = "qdrant_storage"

# Voyage embeddings are configured to produce 512-dimensional vectors.
VECTOR_SIZE = 512


_client: QdrantClient | None = None
_active_collection: str | None = None


def get_qdrant_client() -> QdrantClient:
    """
    Returns one shared Qdrant client for the backend.
    """
    global _client

    if _client is None:
        _client = QdrantClient(
            path=QDRANT_PATH
        )

    return _client


def sanitize_collection_name(
    repository_name: str,
) -> str:
    """
    Converts a repository name into a safe
    Qdrant collection name.
    """

    name = repository_name.strip().lower()

    name = re.sub(
        r"[^a-z0-9_-]+",
        "_",
        name,
    )

    name = name.strip("_")

    if not name:
        name = "repository"

    return f"repo_{name}"


def set_active_collection(
    collection_name: str,
) -> None:
    """
    Marks a repository collection as active.
    """
    global _active_collection

    _active_collection = collection_name


def get_active_collection() -> str:
    """
    Returns the currently active repository collection.
    """

    if not _active_collection:
        raise RuntimeError(
            "No repository is currently active. "
            "Index a repository first."
        )

    return _active_collection


def ensure_repository_collection(
    repository_name: str,
):
    """
    Creates a dedicated Qdrant collection
    for a repository if necessary.
    """

    client = get_qdrant_client()

    collection_name = sanitize_collection_name(
        repository_name
    )

    if not client.collection_exists(
        collection_name
    ):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )

    set_active_collection(
        collection_name
    )

    return client, collection_name


def reset_repository_collection(
    repository_name: str,
):
    """
    Deletes and recreates this repository's
    Qdrant collection.

    This is important when embedding dimensions
    or repository contents change.
    """

    client = get_qdrant_client()

    collection_name = sanitize_collection_name(
        repository_name
    )

    if client.collection_exists(
        collection_name
    ):
        client.delete_collection(
            collection_name=collection_name
        )

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=Distance.COSINE,
        ),
    )

    set_active_collection(
        collection_name
    )

    return client, collection_name