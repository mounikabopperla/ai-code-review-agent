from google import genai

from backend.config.settings import settings


EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSION = 768


client = genai.Client(
    api_key=settings.google_api_key
)


def load_embedding_model():
    """
    Returns the Gemini client and embedding model name.

    The actual embedding computation is handled by
    the Gemini Embeddings API instead of running a
    transformer locally on Railway.
    """

    return client, EMBEDDING_MODEL