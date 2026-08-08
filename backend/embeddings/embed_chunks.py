import json
from pathlib import Path

import torch
from qdrant_client.models import PointStruct

from backend.embeddings.model import load_embedding_model
from backend.vector_store.qdrant_store import (
    reset_repository_collection,
)


DEFAULT_BATCH_SIZE = 4


def load_chunks(chunk_file: str):
    """
    Reads a chunks.jsonl file and returns all chunks.
    """
    chunk_path = Path(chunk_file)

    with chunk_path.open("r", encoding="utf-8") as file:
        return [
            json.loads(line)
            for line in file
        ]


def prepare_chunk_text(chunk: dict) -> str:
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
    tokenizer,
    model,
) -> list[float]:
    """
    Converts one text into one normalized embedding vector.
    """
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=512,
    )

    with torch.no_grad():
        outputs = model(**inputs)

    embedding = outputs.last_hidden_state[:, 0]

    embedding = torch.nn.functional.normalize(
        embedding,
        p=2,
        dim=1,
    )

    return embedding[0].tolist()


def generate_embeddings_batch(
    texts: list[str],
    tokenizer,
    model,
) -> list[list[float]]:
    """
    Converts multiple texts into normalized embeddings
    in one model call.
    """
    inputs = tokenizer(
        texts,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=512,
    )

    with torch.no_grad():
        outputs = model(**inputs)

    embeddings = outputs.last_hidden_state[:, 0]

    embeddings = torch.nn.functional.normalize(
        embeddings,
        p=2,
        dim=1,
    )

    return embeddings.tolist()


def build_payload(chunk: dict) -> dict:
    """
    Creates metadata stored with each vector.
    """
    return {
        "chunk_id": chunk["chunk_id"],
        "file_path": chunk["file_path"],
        "name": chunk["name"],
        "type": chunk["type"],
        "docstring": chunk.get("docstring", ""),
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
    Generates embeddings and stores them in a repository-specific
    Qdrant collection.
    """

    if not chunks:
        return 0

    print(
        f"Indexing {len(chunks)} chunks "
        f"for repository '{repository_name}' "
        f"in batches of {batch_size}..."
    )

    tokenizer, model = load_embedding_model()
    model.eval()

    client, collection_name = reset_repository_collection(
        repository_name
    )

    print(
        f"Using Qdrant collection: {collection_name}"
    )

    total_batches = (
        len(chunks) + batch_size - 1
    ) // batch_size

    for batch_number, start in enumerate(
        range(0, len(chunks), batch_size),
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
            tokenizer,
            model,
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
                    payload=build_payload(chunk),
                )
            )

        client.upsert(
            collection_name=collection_name,
            points=points,
        )

        print(
            f"Batch {batch_number}/{total_batches} "
            f"stored ({end}/{len(chunks)} chunks)"
        )

    print(
        f"Finished storing {len(chunks)} vectors "
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

    stored_count = embed_and_store_chunks(
        chunks,
        repository_name="manual_repository",
    )

    print(
        f"Stored {stored_count} vectors in Qdrant"
    )