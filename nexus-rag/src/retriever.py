"""
Retrieval logic: vector search + relevance threshold filtering.
Never fabricates results — returns exactly what the vector store found.
"""
from typing import List, Dict, Optional
from src import vector_store
from src.config import TOP_K, RELEVANCE_THRESHOLD


def retrieve(query: str, session_id: str, top_k: int = TOP_K, threshold: float = RELEVANCE_THRESHOLD,
             source_filter: Optional[str] = None) -> Dict:
    """
    Returns:
      {
        "chunks": [...],       # chunks that passed the relevance threshold
        "all_candidates": [...],  # everything retrieved, before filtering (for evidence view)
        "grounded": bool,      # whether we have enough relevant context to answer
      }
    """
    candidates = vector_store.search(query, top_k=top_k, session_id=session_id, source_filter=source_filter)
    passing = [c for c in candidates if c["score"] >= threshold]

    return {
        "chunks": passing,
        "all_candidates": candidates,
        "grounded": len(passing) > 0,
    }
