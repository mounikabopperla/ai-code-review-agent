import json
from pathlib import Path

from transformers import AutoModel, AutoTokenizer
import torch

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
)


def load_chunks(chunk_file: str):
    """
    Reads the chunks.jsonl file and returns all chunks as a Python list.
    """

    chunk_path = Path(chunk_file)

    with chunk_path.open("r", encoding="utf-8") as file:
        chunks = [json.loads(line) for line in file]
        return chunks

def prepare_chunk_text(chunk: dict) -> str:
    """
    Combines chunk metadata and source code into one searchable text.
    """
    return f"""
File: {chunk['file_path']}
Name: {chunk['name']}
Type: {chunk['type']}
Docstring: {chunk['docstring']}

Source Code:
{chunk['source_code']}
""".strip()


def load_embedding_model():
    """
    Loads the BGE tokenizer and embedding model.
    """
    model_name = "BAAI/bge-base-en-v1.5"

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)

    return tokenizer, model


def generate_embedding(text: str, tokenizer, model) -> list[float]:
    """
    Converts text into one normalized embedding vector.
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


def create_qdrant_collection():
    """
    Creates a local Qdrant collection for code embeddings.
    """
    client = QdrantClient(path="qdrant_storage")

    collection_name = "code_chunks"

    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=768,
                distance=Distance.COSINE,
            ),
        )

    return client, collection_name


def insert_one_vector(
        client,
        collection_name,
        chunk,
        embedding,
    ):
    """
    Stores one embedding in Qdrant.
    """

    point = PointStruct(
        id=1,
        vector=embedding,
        payload={
            "file_path": chunk["file_path"],
            "name": chunk["name"],
            "type": chunk["type"],
        },
    )

    client.upsert(
        collection_name=collection_name,
        points=[point],
    )


if __name__ == "__main__":
    chunks = load_chunks("chunks.jsonl")
    print(f"Loaded {len(chunks)} chunks")

    sample_text = prepare_chunk_text(chunks[0])
    print(sample_text[:500])

    print("\nLoading BGE embedding model...")

    tokenizer, model = load_embedding_model()

    print("Model loaded successfully!")

    embedding = generate_embedding(
        sample_text,
        tokenizer,
        model,
    )

    print(f"\nEmbedding Dimension: {len(embedding)}")
    print(embedding[:10])

    client, collection_name = create_qdrant_collection()

    for index, chunk in enumerate(chunks):

        text = prepare_chunk_text(chunk)

        embedding = generate_embedding(
            text,
            tokenizer,
            model,
        )

        point = PointStruct(
            id=index,
            vector=embedding,
            payload={
                "file_path": chunk["file_path"],
                "name": chunk["name"],
                "type": chunk["type"],
            },
        )

        client.upsert(
            collection_name=collection_name,
            points=[point],
        )

    print(f"Stored {len(chunks)} vectors in Qdrant")

