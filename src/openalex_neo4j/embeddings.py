"""Embedding generation for semantic search."""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Lazy import to avoid loading if not needed
_model = None


def get_embedding_model():
    """Get or initialize the sentence transformer model.

    Returns:
        SentenceTransformer model

    Raises:
        ImportError: If sentence-transformers is not installed
    """
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading embedding model: all-MiniLM-L6-v2")
            _model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Embedding model loaded successfully")
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for embeddings. "
                "Install with: uv pip install sentence-transformers torch"
            )
    return _model


def generate_embedding(text: str) -> list[float] | None:
    """Generate embedding vector for text.

    Args:
        text: Input text to embed

    Returns:
        Embedding vector as list of floats, or None if text is empty
    """
    if not text or not text.strip():
        return None

    try:
        model = get_embedding_model()
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        return None


def generate_work_embedding(title: str, abstract: str | None = None) -> list[float] | None:
    """Generate embedding for a work based on title and abstract.

    Args:
        title: Work title
        abstract: Work abstract (optional)

    Returns:
        Embedding vector combining title and abstract
    """
    if not title:
        return None

    # Combine title and abstract for richer embedding
    if abstract:
        text = f"{title}. {abstract[:1000]}"  # Limit abstract to 1000 chars
    else:
        text = title

    return generate_embedding(text)


def generate_batch_embeddings(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """Generate embeddings for multiple texts efficiently.

    Args:
        texts: List of texts to embed
        batch_size: Batch size for encoding

    Returns:
        List of embedding vectors
    """
    if not texts:
        return []

    try:
        model = get_embedding_model()
        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > 100
        )
        return [emb.tolist() for emb in embeddings]
    except Exception as e:
        logger.error(f"Failed to generate batch embeddings: {e}")
        return [[] for _ in texts]
