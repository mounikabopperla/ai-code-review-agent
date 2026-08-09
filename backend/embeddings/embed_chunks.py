import json
import logging
from pathlib import Path

from qdrant_client.models import PointStruct

from backend.embeddings.model import (
    EMBEDDING_DIMENSION,
    load_embedding_model,
)
from backend.vector_store.qdrant_store import (
    reset_repository_collection,
)


logger = logging.getLogger("embed-chunks")

# Voyage recommends sending multiple documents per request
# to improve throughput and reduce request count.
DEFAULT_BATCH_SIZE = 64


def load_chunks(chunk_file: str):
    """
    Reads a chunks.jsonl file and returns all chunks.
    """

    chunk_path = Path(chunk_file)

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
    Combines chunk metadata and content into searchable text.
    """

    return f"""
File: {chunk["file_path"]}
Name: {chunk["name"]}
Type: {chunk["type"]}
Docstring: {chunk.get("docstring", "")}

Source Code / Documentation:
{chunk["source_code"]}
""".strip()


def generate_embedding(
    text: str,
    client,
    model_name: str,
) -> list[float]:
    """
    Generates one embedding for a user query.
    """

    result = client.embed(
        [text],
        model=model_name,
        input_type="query",
        output_dimension=EMBEDDING_DIMENSION,
    )

    return result.embeddings[0]


def generate_embeddings_batch(
    texts: list[str],
    client,
    model_name: str,
) -> list[list[float]]:
    """
    Generates embeddings for repository chunks.

    All texts in this call are treated as retrieval documents.
    """

    result = client.embed(
        texts,
        model=model_name,
        input_type="document",
        output_dimension=EMBEDDING_DIMENSION,
    )

    return result.embeddings


def build_payload(
    chunk: dict,
) -> dict:
    """
    Creates metadata stored with each vector.
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
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> int:
    """
    Generates Voyage embeddings and stores them
    in a repository-specific Qdrant collection.
    """

    if not chunks:
        return 0

    print(
        f"Indexing {len(chunks)} chunks "
        f"for repository '{repository_name}' "
        f"in batches of {batch_size}..."
    )

    client, model_name = load_embedding_model()

    qdrant_client, collection_name = (
        reset_repository_collection(
            repository_name
        )
    )

    print(
        f"Using Qdrant collection: "
        f"{collection_name}"
    )

    total_batches = (
        len(chunks)
        + batch_size
        - 1
    ) // batch_size

    for batch_number, start in enumerate(
        range(
            0,
            len(chunks),
            batch_size,
        ),
        start=1,
    ):
        end = min(
            start + batch_size,
            len(chunks),
        )

        batch_chunks = chunks[start:end]

        texts = [
            prepare_chunk_text(chunk)
            for chunk in batch_chunks
        ]

        embeddings = generate_embeddings_batch(
            texts,
            client,
            model_name,
        )

        points = []

        for offset, (
            chunk,
            embedding,
        ) in enumerate(
            zip(
                batch_chunks,
                embeddings,
            )
        ):
            point_id = start + offset

            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=build_payload(
                        chunk
                    ),
                )
            )

        qdrant_client.upsert(
            collection_name=collection_name,
            points=points,
        )

        print(
            f"Batch "
            f"{batch_number}/"
            f"{total_batches} "
            f"stored "
            f"({end}/{len(chunks)} chunks)"
        )

    print(
        f"Finished storing "
        f"{len(chunks)} vectors "
        f"in {collection_name}."
    )

    return len(chunks)


if __name__ == "__main__":
    chunks = load_chunks(
        "chunks.jsonl"
    )

    print(
        f"Loaded {len(chunks)} chunks"
    )

    stored_count = (
        embed_and_store_chunks(
            chunks,
            repository_name=(
                "manual_repository"
            ),
        )
    )

    print(
        f"Stored {stored_count} "
        f"vectors in Qdrant"
    )