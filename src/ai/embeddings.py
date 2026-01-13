# neural-inbox1/src/ai/embeddings.py
"""Vector embeddings for semantic search."""
import logging
from typing import List, Optional

from openai import AsyncOpenAI
from src.config import config

logger = logging.getLogger(__name__)

# Singleton client
_client: Optional[AsyncOpenAI] = None


def _get_client() -> AsyncOpenAI:
    """Get or create OpenAI client."""
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=config.openai.api_key)
    return _client


async def get_embedding(text: str) -> List[float]:
    """
    Get embedding vector for text using OpenAI.

    Args:
        text: Input text to embed

    Returns:
        List of floats (1536 dimensions for text-embedding-3-small)
    """
    if not text or not text.strip():
        logger.warning("Empty text provided for embedding")
        return []

    # Truncate if too long (8191 tokens max for text-embedding-3-small)
    # Rough estimate: 1 token ~ 4 chars for Russian
    max_chars = 30000
    if len(text) > max_chars:
        text = text[:max_chars]
        logger.warning(f"Text truncated to {max_chars} chars for embedding")

    try:
        client = _get_client()
        response = await client.embeddings.create(
            model=config.openai.embedding_model,
            input=text.strip()
        )
        return response.data[0].embedding

    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return []


async def get_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Get embeddings for multiple texts in one API call.

    Args:
        texts: List of texts to embed

    Returns:
        List of embedding vectors (same order as input)
    """
    if not texts:
        return []

    # Filter and prepare texts
    prepared = []
    indices = []
    for i, text in enumerate(texts):
        if text and text.strip():
            prepared.append(text.strip()[:30000])
            indices.append(i)

    if not prepared:
        return [[] for _ in texts]

    try:
        client = _get_client()
        response = await client.embeddings.create(
            model=config.openai.embedding_model,
            input=prepared
        )

        # Map results back to original indices
        results = [[] for _ in texts]
        for j, embedding_data in enumerate(response.data):
            original_idx = indices[j]
            results[original_idx] = embedding_data.embedding

        return results

    except Exception as e:
        logger.error(f"Batch embedding error: {e}")
        return [[] for _ in texts]
