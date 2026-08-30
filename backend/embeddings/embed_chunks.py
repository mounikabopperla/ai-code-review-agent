import json
from pathlib import Path

from fastembed import SparseTextEmbedding
from qdrant_client.models import (
    PointStruct,
    SparseVector,
)

from backend.vector_store.qdrant_store import (
    SPARSE_VECTOR_NAME,
    reset_repository_collection,
)


BM25_MODEL_NAME = "Qdrant/bm25"

_sparse_model: SparseTextEmbedding | None = None


def load_sparse_model() -> SparseTextEmbedding:
    """
    Loads the local FastEmbed BM25 model once
    and reuses it for later requests.
    """

    global _sparse_model

    if _sparse_model is None:
        _sparse_model = SparseTextEmbedding(
            model_name=BM25_MODEL_NAME
        )

    return _sparse_model


def load_chunks(
    chunk_file: str,
):
    """
    Reads a chunks.jsonl file and returns all chunks.
    """

    chunk_path = Path(
        chunk_file
    )

    with chunk_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return [
            json.loads(line)
            for line in file
        ]


def prepare_chunk_text(
    chunk: dict,
) -> str:
    """
    Combines useful repository metadata and source
    content into searchable text.
    """

    return f"""
File: {chunk["file_path"]}
Name: {chunk["name"]}
Type: {chunk["type"]}
Docstring: {chunk.get("docstring", "")}

Source Code / Documentation:

{chunk["source_code"]}
""".strip()


def _to_sparse_vector(
    embedding,
) -> SparseVector:
    """
    Converts a FastEmbed sparse result into the
    sparse-vector format expected by Qdrant.
    """

    return SparseVector(
        indices=[
            int(index)
            for index in embedding.indices
        ],
        values=[
            float(value)
            for value in embedding.values
        ],
    )


def generate_embedding(
    text: str,
    client=None,
    model_name=None,
) -> SparseVector:
    """
    Generates one local BM25 sparse vector.

    client and model_name are accepted temporarily
    for compatibility with the previous Voyage API
    function signature. They are no longer used.
    """

    del client
    del model_name

    model = load_sparse_model()

    embedding = next(
        iter(
            model.embed(
                [text]
            )
        )
    )

    return _to_sparse_vector(
        embedding
    )


def generate_embeddings_batch(
    texts: list[str],
    client=None,
    model_name=None,
) -> list[SparseVector]:
    """
    Generates local BM25 sparse vectors for multiple
    pieces of repository content.

    No external API calls or rate-limit waits occur.
    """

    del client
    del model_name

    if not texts:
        return []

    model = load_sparse_model()

    embeddings = model.embed(
        texts
    )

    return [
        _to_sparse_vector(
            embedding
        )
        for embedding in embeddings
    ]


def build_payload(
    chunk: dict,
) -> dict:
    """
    Creates the metadata stored with each vector.
    """

    return {
        "chunk_id": chunk["chunk_id"],
        "file_path": chunk["file_path"],
        "name": chunk["name"],
        "type": chunk["type"],
        "docstring": chunk.get(
            "docstring",
            "",
        ),
        "source_code": chunk["source_code"],
        "start_line": chunk["start_line"],
        "end_line": chunk["end_line"],
    }


def embed_and_store_chunks(
    chunks: list[dict],
    repository_name: str,
) -> int:
    """
    Generates local BM25 sparse vectors and stores
    them in the repository's Qdrant collection.

    This replaces the previous Voyage embedding path.
    No hosted embedding API is required.
    """

    if not chunks:
        return 0

    print(
        f"Indexing {len(chunks)} chunks "
        f"for repository '{repository_name}' "
        f"using local BM25."
    )

    texts = [
        prepare_chunk_text(
            chunk
        )
        for chunk in chunks
    ]

    print(
        "Generating local BM25 sparse vectors..."
    )

    embeddings = generate_embeddings_batch(
        texts
    )

    qdrant_client, collection_name = (
        reset_repository_collection(
            repository_name
        )
    )

    print(
        f"Using Qdrant collection: "
        f"{collection_name}"
    )

    points = []

    for point_id, (
        chunk,
        embedding,
    ) in enumerate(
        zip(
            chunks,
            embeddings,
        )
    ):
        points.append(
            PointStruct(
                id=point_id,
                vector={
                    SPARSE_VECTOR_NAME: embedding,
                },
                payload=build_payload(
                    chunk
                ),
            )
        )

    # Store in moderate batches so larger repositories
    # do not create one enormous Qdrant request.
    batch_size = 100
    stored_count = 0

    for start in range(
        0,
        len(points),
        batch_size,
    ):
        batch = points[
            start:start + batch_size
        ]

        qdrant_client.upsert(
            collection_name=collection_name,
            points=batch,
        )

        stored_count += len(batch)

        print(
            f"Stored {stored_count}/"
            f"{len(points)} BM25 vectors."
        )

    print(
        f"Finished storing "
        f"{stored_count} sparse vectors "
        f"in {collection_name}."
    )

    return stored_count


if __name__ == "__main__":
    chunks = load_chunks(
        "chunks.jsonl"
    )

    print(
        f"Loaded {len(chunks)} chunks"
    )

    stored_count = embed_and_store_chunks(
        chunks,
        repository_name="manual_repository",
    )

    print(
        f"Stored {stored_count} "
        f"vectors in Qdrant"
    )