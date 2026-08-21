"""
ChromaDB persistent vector store.
Stores embedding + text + source + page + scope metadata.

Every chunk carries a "scope": either BASE_SCOPE (the permanent, provided
knowledge base, shared by every chat) or a chat session_id (temporary uploads
belonging to one chat). Searches run across a list of scopes, so a chat can
query the provided documents and its own uploads together while staying
isolated from other chats' uploads.
"""
from typing import List, Dict, Optional
import chromadb
from src.config import VECTOR_DIR, COLLECTION_NAME, BASE_SCOPE
from src.embeddings import embed_texts, embed_query

_client = None
_collection = None


def _get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=VECTOR_DIR)
    return _client


def _get_collection():
    global _collection
    if _collection is None:
        client = _get_client()
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _scope_filter(scopes: List[str]) -> Dict:
    """Chroma metadata filter matching any of the given scopes."""
    if len(scopes) == 1:
        return {"scope": scopes[0]}
    return {"scope": {"$in": list(scopes)}}


def _where(scopes: List[str], source_filter: Optional[str] = None) -> Dict:
    scope_clause = _scope_filter(scopes)
    if not source_filter:
        return scope_clause
    return {"$and": [scope_clause, {"source": source_filter}]}


def count_for_scopes(scopes: List[str]) -> int:
    """How many chunks are stored across the given scopes."""
    try:
        collection = _get_collection()
        if collection.count() == 0:
            return 0
        result = collection.get(where=_where(scopes), include=[])
        return len(result.get("ids", []))
    except Exception:
        return 0


def is_indexed(scopes: List[str]) -> bool:
    return count_for_scopes(scopes) > 0


def add_chunks(chunk_records: List[Dict], scope: str):
    """
    chunk_records: [{chunk_id, source, page, text}, ...]
    Embeds and stores them under the given scope.
    """
    if not chunk_records:
        return

    collection = _get_collection()
    texts = [c["text"] for c in chunk_records]
    vectors = embed_texts(texts)

    # Prefix the id with the scope so chunk_ids can't collide across scopes
    # (e.g. two chats both uploading a file with the same name).
    ids = [f"{scope}::{c['chunk_id']}" for c in chunk_records]
    metadatas = [
        {"source": c["source"], "page": c["page"] if c["page"] is not None else -1,
         "chunk_id": c["chunk_id"], "scope": scope}
        for c in chunk_records
    ]

    # Chroma has a max batch size; chunk the inserts defensively.
    BATCH = 200
    for i in range(0, len(ids), BATCH):
        collection.add(
            ids=ids[i:i + BATCH],
            embeddings=vectors[i:i + BATCH],
            documents=texts[i:i + BATCH],
            metadatas=metadatas[i:i + BATCH],
        )


def delete_scope(scope: str):
    """Removes every chunk in one scope. Used to drop a chat's uploads, or to
    rebuild the base knowledge base from scratch."""
    try:
        collection = _get_collection()
        if collection.count() > 0:
            collection.delete(where={"scope": scope})
    except Exception as e:
        print(f"[vector_store] WARNING: couldn't delete scope {scope}: {e}")


def sources_in_scopes(scopes: List[str]) -> List[str]:
    """Distinct source filenames that actually have chunks in the index."""
    try:
        collection = _get_collection()
        if collection.count() == 0:
            return []
        result = collection.get(where=_where(scopes), include=["metadatas"])
        return sorted({m["source"] for m in result.get("metadatas", []) if m.get("source")})
    except Exception:
        return []


def search(query: str, top_k: int, scopes: List[str],
           source_filter: Optional[str] = None) -> List[Dict]:
    """
    Returns [{id, text, source, page, chunk_id, scope, score}, ...] sorted by relevance,
    restricted to the given scopes.
    score is a cosine similarity in [0, 1] — 1.0 is an exact semantic match.
    """
    collection = _get_collection()
    if collection.count() == 0:
        return []

    query_vector = embed_query(query)

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=min(top_k, collection.count()),
        where=_where(scopes, source_filter),
    )

    output = []
    if not results["ids"] or not results["ids"][0]:
        return output

    for i in range(len(results["ids"][0])):
        distance = results["distances"][0][i]  # cosine distance, 0 = identical
        score = max(0.0, 1.0 - distance)        # convert to cosine similarity
        meta = results["metadatas"][0][i]
        page = meta.get("page")
        output.append({
            "id": results["ids"][0][i],
            "text": results["documents"][0][i],
            "source": meta.get("source"),
            "page": None if page == -1 else page,
            "chunk_id": meta.get("chunk_id"),
            "scope": meta.get("scope"),
            "score": round(score, 3),
        })

    return output
