"""
2D projection of the knowledge base for the Information panel's semantic map.

Every chunk already has an embedding in Chroma, so the map needs no LLM call and
no extra model: we fetch those vectors, fit a PCA down to two components, and
hand the frontend plain x/y coordinates in [0, 1] that it can draw as an SVG
scatter. The same fitted projection is reused for the query vector, so a question
can be placed on the map next to the chunks it actually retrieved.

PCA is chosen over t-SNE/UMAP deliberately: it is deterministic (the map doesn't
jump between reloads), it is cheap, and it can transform a new query vector with
the projection fitted on the corpus — which neither t-SNE nor UMAP does natively.
"""
from typing import List, Dict, Optional, Tuple
import numpy as np

from src import vector_store
from src.vector_store import _get_collection, _where

# Cache the fitted projection so we don't refit on every question. Keyed by the
# scopes and the chunk count, so adding an upload invalidates it automatically.
_cache_key: Optional[Tuple] = None
_cache_model = None
_cache_points: List[Dict] = []
_cache_bounds: Optional[Tuple[np.ndarray, np.ndarray]] = None


def _normalize(coords: np.ndarray) -> Tuple[np.ndarray, Tuple[np.ndarray, np.ndarray]]:
    """Scale coordinates into [0, 1] on both axes, tolerating degenerate spreads."""
    lo = coords.min(axis=0)
    hi = coords.max(axis=0)
    span = hi - lo
    # A single point, or a corpus with no variance on an axis, would divide by 0.
    span[span == 0] = 1.0
    return (coords - lo) / span, (lo, span)


def _fit(scopes: List[str]):
    """Fetch embeddings for the scopes and fit the 2D projection. Cached."""
    global _cache_key, _cache_model, _cache_points, _cache_bounds

    collection = _get_collection()
    total = collection.count()
    if total == 0:
        return [], None, None

    result = collection.get(where=_where(scopes), include=["embeddings", "metadatas"])
    ids = result.get("ids", [])
    if not ids:
        return [], None, None

    key = (tuple(scopes), len(ids), total)
    if key == _cache_key:
        return _cache_points, _cache_model, _cache_bounds

    vectors = np.asarray(result["embeddings"], dtype=float)
    metas = result["metadatas"]

    model = None
    if len(ids) >= 3:
        from sklearn.decomposition import PCA
        model = PCA(n_components=2, random_state=0)
        coords = model.fit_transform(vectors)
    elif len(ids) == 2:
        # Two points: PCA to 2D is degenerate, so lay them out on a line.
        coords = np.array([[0.0, 0.0], [1.0, 1.0]])
    else:
        coords = np.array([[0.5, 0.5]])

    coords, bounds = _normalize(coords)

    points = []
    for i, chunk_id in enumerate(ids):
        meta = metas[i]
        page = meta.get("page")
        points.append({
            "id": chunk_id,
            "chunk_id": meta.get("chunk_id"),
            "x": round(float(coords[i][0]), 4),
            "y": round(float(coords[i][1]), 4),
            "source": meta.get("source"),
            "page": None if page == -1 else page,
            "scope": meta.get("scope"),
        })

    _cache_key, _cache_model, _cache_points, _cache_bounds = key, model, points, bounds
    return points, model, bounds


def corpus_points(scopes: List[str]) -> List[Dict]:
    """Every chunk in the given scopes, positioned on the map."""
    points, _, _ = _fit(scopes)
    return points


def project_query(query: str, scopes: List[str]) -> Optional[Dict]:
    """
    Place a question on the same map as the corpus, so the UI can draw it next to
    the chunks it retrieved. Returns None when the corpus is too small to have a
    real fitted projection.
    """
    points, model, bounds = _fit(scopes)
    if model is None or bounds is None or not points:
        return None

    from src.embeddings import embed_query
    vector = np.asarray([embed_query(query)], dtype=float)
    coords = model.transform(vector)

    lo, span = bounds
    normalized = (coords[0] - lo) / span
    # A query can land outside the corpus hull; clamp so it stays inside the plot.
    return {
        "x": round(float(np.clip(normalized[0], 0.0, 1.0)), 4),
        "y": round(float(np.clip(normalized[1], 0.0, 1.0)), 4),
    }


def invalidate():
    """Drop the cached projection — called after the index changes."""
    global _cache_key, _cache_model, _cache_points, _cache_bounds
    _cache_key = _cache_model = _cache_bounds = None
    _cache_points = []
