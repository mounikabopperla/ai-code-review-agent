import voyageai

from backend.config.settings import settings


EMBEDDING_MODEL = "voyage-3.5-lite"
EMBEDDING_DIMENSION = 512


def load_embedding_model():
    """
    Creates the Voyage AI client used for embeddings.
    """

    client = voyageai.Client(
        api_key=settings.voyage_api_key
    )

    return client, EMBEDDING_MODEL