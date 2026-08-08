from transformers import AutoTokenizer, AutoModel


def load_embedding_model():
    model_name = "BAAI/bge-base-en-v1.5"

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)

    return tokenizer, model