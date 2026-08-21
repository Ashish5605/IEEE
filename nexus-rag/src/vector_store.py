"""
ChromaDB persistent vector store.
Stores embedding + text + source + page + chunk_id metadata.
Supports metadata filtering for document-scoped search.
"""
from typing import List, Dict, Optional
import chromadb
from src.config import VECTOR_DIR, COLLECTION_NAME
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


def is_indexed() -> bool:
    """Whether the knowledge base has already been embedded and stored."""
    try:
        return _get_collection().count() > 0
    except Exception:
        return False


def indexed_chunk_count() -> int:
    try:
        return _get_collection().count()
    except Exception:
        return 0


def session_chunk_count(session_id: str) -> int:
    """Chunk count scoped to one chat session's knowledge base."""
    try:
        collection = _get_collection()
        if collection.count() == 0:
            return 0
        result = collection.get(where={"session_id": session_id}, include=[])
        return len(result.get("ids", []))
    except Exception:
        return 0


def is_session_indexed(session_id: str) -> bool:
    return session_chunk_count(session_id) > 0


def reset_index():
    """Wipe the collection so it can be rebuilt from scratch."""
    global _collection
    client = _get_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    _collection = None
    _get_collection()


def add_chunks(chunk_records: List[Dict], session_id: str):
    """
    chunk_records: [{chunk_id, source, page, text}, ...]
    Embeds and stores them with full metadata, scoped to a session_id so
    each chat's knowledge base stays isolated from every other chat's.
    """
    if not chunk_records:
        return

    collection = _get_collection()
    texts = [c["text"] for c in chunk_records]
    vectors = embed_texts(texts)

    # Prefix the id with session_id so chunk_ids can't collide across sessions
    # (e.g. two chats both uploading a file with the same name).
    ids = [f"{session_id}::{c['chunk_id']}" for c in chunk_records]
    metadatas = [
        {"source": c["source"], "page": c["page"] if c["page"] is not None else -1,
         "chunk_id": c["chunk_id"], "session_id": session_id}
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


def delete_session(session_id: str):
    """Removes every chunk belonging to one chat session's knowledge base."""
    try:
        collection = _get_collection()
        if collection.count() > 0:
            collection.delete(where={"session_id": session_id})
    except Exception as e:
        print(f"[vector_store] WARNING: couldn't delete session {session_id}: {e}")


def search(query: str, top_k: int, session_id: str, source_filter: Optional[str] = None) -> List[Dict]:
    """
    Returns [{text, source, page, chunk_id, score}, ...] sorted by relevance,
    scoped to one chat session's knowledge base only.
    score is a cosine-similarity-derived relevance value in [0, 1].
    """
    collection = _get_collection()
    if collection.count() == 0:
        return []

    query_vector = embed_query(query)
    where = {"session_id": session_id} if not source_filter else {
        "$and": [{"session_id": session_id}, {"source": source_filter}]
    }

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=min(top_k, collection.count()),
        where=where,
    )

    output = []
    if not results["ids"] or not results["ids"][0]:
        return output

    for i in range(len(results["ids"][0])):
        distance = results["distances"][0][i]  # cosine distance, 0 = identical
        score = max(0.0, 1.0 - distance)        # convert to similarity-ish score
        meta = results["metadatas"][0][i]
        page = meta.get("page")
        output.append({
            "text": results["documents"][0][i],
            "source": meta.get("source"),
            "page": None if page == -1 else page,
            "chunk_id": meta.get("chunk_id"),
            "score": round(score, 3),
        })

    return output
