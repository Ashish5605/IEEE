"""
Embedding model wrapper.
Uses sentence-transformers locally (free, offline after first download).
Configurable via EMBEDDING_MODEL in .env — swap models without touching
any other file.
"""
from typing import List
from src.config import EMBEDDING_MODEL

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        print(f"[embeddings] Loading embedding model: {EMBEDDING_MODEL} (first run downloads it)")
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a batch of texts. Used for indexing chunks."""
    if not texts:
        return []
    model = _get_model()
    vectors = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return vectors.tolist()


def embed_query(text: str) -> List[float]:
    """Embed a single query string."""
    return embed_texts([text])[0]
