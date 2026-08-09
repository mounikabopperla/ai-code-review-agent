"""
Voyage AI embedding utilities.

This version is designed to work with the restricted
free/no-payment-method Voyage API limits.

It:
1. Groups chunks by an approximate token budget.
2. Sends multiple chunks in each Voyage request.
3. Spaces requests apart to respect the RPM limit.
4. Retries automatically if Voyage returns a 429.
"""

import json
import logging
import time
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


# ---------------------------------------------------------
# Free-tier / restricted-account safety settings
# ---------------------------------------------------------

# Your current Voyage account reported 3 RPM.
# 21 seconds between requests keeps us below 3/minute.
MIN_SECONDS_BETWEEN_REQUESTS = 21.0

# Your current account reported 10K TPM.
# Keep each request conservative so 3 requests/minute
# remain below that limit.
MAX_APPROX_TOKENS_PER_REQUEST = 2800

# Additional safety limit for number of chunks/request.
MAX_TEXTS_PER_REQUEST = 32

# Retry settings for temporary 429/rate-limit errors.
MAX_RETRIES = 3
RATE_LIMIT_RETRY_SECONDS = 65


_last_request_time = 0.0


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
    Combines useful chunk metadata and source code
    into the text sent to Voyage.
    """

    return f"""
File: {chunk["file_path"]}
Name: {chunk["name"]}
Type: {chunk["type"]}
Docstring: {chunk.get("docstring", "")}

Source Code / Documentation:
{chunk["source_code"]}
""".strip()


def approximate_tokens(
    text: str,
) -> int:
    """
    Estimates token count without requiring another
    tokenizer dependency.

    Four characters per token is used only as a
    conservative scheduling estimate.
    """

    return max(
        1,
        len(text) // 4,
    )


def wait_for_rate_limit():
    """
    Makes sure Voyage requests are spaced apart.

    This prevents us from rapidly sending requests
    and hitting the restricted RPM limit.
    """

    global _last_request_time

    if _last_request_time == 0:
        return

    elapsed = (
        time.monotonic()
        - _last_request_time
    )

    remaining = (
        MIN_SECONDS_BETWEEN_REQUESTS
        - elapsed
    )

    if remaining > 0:
        logger.info(
            "Waiting %.1f seconds for "
            "Voyage free-tier rate limit...",
            remaining,
        )

        time.sleep(
            remaining
        )


def mark_request_sent():
    """
    Records when the latest Voyage request occurred.
    """

    global _last_request_time

    _last_request_time = (
        time.monotonic()
    )


def build_embedding_batches(
    chunks: list[dict],
) -> list[list[dict]]:
    """
    Groups repository chunks into batches while
    respecting an approximate token budget.

    A batch ends when either:
    - it reaches MAX_TEXTS_PER_REQUEST, or
    - adding another chunk would exceed the
      approximate token budget.
    """

    batches = []

    current_batch = []
    current_tokens = 0

    for chunk in chunks:
        text = prepare_chunk_text(
            chunk
        )

        token_count = (
            approximate_tokens(
                text
            )
        )

        # If one chunk itself is extremely large,
        # allow it as its own batch.
        would_exceed_tokens = (
            current_batch
            and (
                current_tokens
                + token_count
                > MAX_APPROX_TOKENS_PER_REQUEST
            )
        )

        would_exceed_items = (
            len(current_batch)
            >= MAX_TEXTS_PER_REQUEST
        )

        if (
            would_exceed_tokens
            or would_exceed_items
        ):
            batches.append(
                current_batch
            )

            current_batch = []
            current_tokens = 0

        current_batch.append(
            chunk
        )

        current_tokens += (
            token_count
        )

    if current_batch:
        batches.append(
            current_batch
        )

    return batches


def voyage_embed_with_retry(
    *,
    texts: list[str],
    client,
    model_name: str,
    input_type: str,
) -> list[list[float]]:
    """
    Calls Voyage while respecting our request spacing.

    If Voyage returns a rate-limit error, waits and retries.
    """

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):
        wait_for_rate_limit()

        try:
            result = client.embed(
                texts,
                model=model_name,
                input_type=input_type,
                output_dimension=(
                    EMBEDDING_DIMENSION
                ),
            )

            mark_request_sent()

            return result.embeddings

        except Exception as error:
            mark_request_sent()

            error_text = str(
                error
            ).lower()

            is_rate_limit = (
                "429" in error_text
                or "rate limit" in error_text
                or "too many requests"
                in error_text
            )

            if (
                not is_rate_limit
                or attempt
                == MAX_RETRIES
            ):
                raise

            logger.warning(
                "Voyage rate limit reached. "
                "Waiting %s seconds before "
                "retry %s/%s.",
                RATE_LIMIT_RETRY_SECONDS,
                attempt + 1,
                MAX_RETRIES,
            )

            time.sleep(
                RATE_LIMIT_RETRY_SECONDS
            )

    raise RuntimeError(
        "Voyage embedding request failed."
    )


def generate_embedding(
    text: str,
    client,
    model_name: str,
) -> list[float]:
    """
    Generates one embedding for a user's question.
    """

    embeddings = (
        voyage_embed_with_retry(
            texts=[text],
            client=client,
            model_name=model_name,
            input_type="query",
        )
    )

    return embeddings[0]


def generate_embeddings_batch(
    texts: list[str],
    client,
    model_name: str,
) -> list[list[float]]:
    """
    Generates embeddings for repository chunks.
    """

    return voyage_embed_with_retry(
        texts=texts,
        client=client,
        model_name=model_name,
        input_type="document",
    )


def build_payload(
    chunk: dict,
) -> dict:
    """
    Creates the metadata stored with each vector.
    """

    return {
        "chunk_id": (
            chunk["chunk_id"]
        ),
        "file_path": (
            chunk["file_path"]
        ),
        "name": (
            chunk["name"]
        ),
        "type": (
            chunk["type"]
        ),
        "docstring": chunk.get(
            "docstring",
            "",
        ),
        "source_code": (
            chunk["source_code"]
        ),
        "start_line": (
            chunk["start_line"]
        ),
        "end_line": (
            chunk["end_line"]
        ),
    }


def embed_and_store_chunks(
    chunks: list[dict],
    repository_name: str,
) -> int:
    """
    Generates Voyage embeddings and stores them
    in the repository's Qdrant collection.
    """

    if not chunks:
        return 0

    client, model_name = (
        load_embedding_model()
    )

    batches = (
        build_embedding_batches(
            chunks
        )
    )

    print(
        f"Indexing {len(chunks)} chunks "
        f"for repository "
        f"'{repository_name}'."
    )

    print(
        f"Created {len(batches)} "
        f"Voyage API batches."
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

    stored_count = 0

    for (
        batch_number,
        batch_chunks,
    ) in enumerate(
        batches,
        start=1,
    ):
        texts = [
            prepare_chunk_text(
                chunk
            )
            for chunk in batch_chunks
        ]

        approximate_batch_tokens = sum(
            approximate_tokens(
                text
            )
            for text in texts
        )

        print(
            f"Voyage batch "
            f"{batch_number}/"
            f"{len(batches)} "
            f"starting "
            f"({len(batch_chunks)} chunks, "
            f"~{approximate_batch_tokens} tokens)"
        )

        embeddings = (
            generate_embeddings_batch(
                texts,
                client,
                model_name,
            )
        )

        points = []

        for (
            chunk,
            embedding,
        ) in zip(
            batch_chunks,
            embeddings,
        ):
            point_id = (
                stored_count
                + len(points)
            )

            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=(
                        build_payload(
                            chunk
                        )
                    ),
                )
            )

        qdrant_client.upsert(
            collection_name=(
                collection_name
            ),
            points=points,
        )

        stored_count += len(
            batch_chunks
        )

        print(
            f"Voyage batch "
            f"{batch_number}/"
            f"{len(batches)} stored "
            f"({stored_count}/"
            f"{len(chunks)} chunks)"
        )

    print(
        f"Finished storing "
        f"{stored_count} vectors "
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