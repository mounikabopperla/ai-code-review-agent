from transformers import AutoModel, AutoTokenizer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def load_embedding_model():
    """
    Loads the lightweight MiniLM embedding model.

    Output embedding dimension: 384
    """
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME
    )

    model = AutoModel.from_pretrained(
        MODEL_NAME
    )

    model.eval()

    return tokenizer, model