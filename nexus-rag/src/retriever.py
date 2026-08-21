"""
Retrieval logic: vector search + relevance threshold filtering.
Never fabricates results — returns exactly what the vector store found.
"""
from typing import List, Dict, Optional
from src import vector_store
from src.config import TOP_K, RELEVANCE_THRESHOLD


def retrieve(query: str, scopes: List[str], top_k: int = TOP_K,
             threshold: float = RELEVANCE_THRESHOLD,
             source_filter: Optional[str] = None) -> Dict:
    """
    Searches the given scopes (typically the shared base knowledge base plus the
    current chat's uploads) and splits the hits on the relevance threshold.

    Returns:
      {
        "chunks": [...],          # chunks that passed the relevance threshold
        "all_candidates": [...],  # everything retrieved, before filtering (for evidence view)
        "grounded": bool,         # whether we have enough relevant context to answer
      }
    """
    candidates = vector_store.search(query, top_k=top_k, scopes=scopes,
                                     source_filter=source_filter)
    passing = [c for c in candidates if c["score"] >= threshold]

    return {
        "chunks": passing,
        "all_candidates": candidates,
        "grounded": len(passing) > 0,
    }
