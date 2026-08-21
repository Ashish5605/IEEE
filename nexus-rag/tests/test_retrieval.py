"""
Retrieval tests. Run with: pytest tests/test_retrieval.py
The provided knowledge base is indexed automatically by setup_module.
"""
from src import retriever, indexer, vector_store
from src.config import BASE_SCOPE


def setup_module(module):
    indexer.ensure_base_index()


BASE_ONLY = [BASE_SCOPE]


def test_base_knowledge_base_is_indexed():
    assert vector_store.is_indexed(BASE_ONLY)
    assert vector_store.count_for_scopes(BASE_ONLY) > 0


def test_relevant_question_returns_grounded_result():
    result = retriever.retrieve("What is the minimum attendance requirement?", scopes=BASE_ONLY)
    assert result["grounded"] is True
    assert len(result["chunks"]) > 0


def test_irrelevant_question_is_not_grounded():
    result = retriever.retrieve("What is the population of Japan?", scopes=BASE_ONLY, threshold=0.6)
    # Should either be empty or below threshold — never confidently grounded on unrelated content
    assert result["grounded"] is False or all(c["score"] < 0.6 for c in result["all_candidates"])


def test_cross_language_question_still_retrieves_english_chunk():
    # Tamil phrasing of an attendance question should still hit the English source chunk
    result = retriever.retrieve("குறைந்தபட்ச வருகைத் தேவை என்ன?", scopes=BASE_ONLY, threshold=0.2)
    assert len(result["all_candidates"]) > 0


def test_document_filter_restricts_results():
    docs = vector_store.search("attendance", top_k=5, scopes=BASE_ONLY)
    assert docs, "expected the provided knowledge base to return candidates"
    source = docs[0]["source"]
    filtered = retriever.retrieve("attendance", scopes=BASE_ONLY, source_filter=source)
    assert all(c["source"] == source for c in filtered["chunks"])


def test_every_base_chunk_is_tagged_with_the_base_scope():
    hits = vector_store.search("attendance", top_k=5, scopes=BASE_ONLY)
    assert hits
    assert all(h["scope"] == BASE_SCOPE for h in hits)


def test_session_scope_is_isolated_from_other_sessions():
    """One chat's uploads must never surface in another chat's search."""
    records = [{"chunk_id": "secret_1", "source": "secret.txt", "page": None,
                "text": "The confidential launch code for project bluebird is 4417."}]
    vector_store.add_chunks(records, scope="session-A")
    try:
        # Chat A searches base + its own uploads and finds it.
        hits_a = vector_store.search("bluebird launch code", top_k=5,
                                     scopes=[BASE_SCOPE, "session-A"])
        assert any(h["source"] == "secret.txt" for h in hits_a)

        # Chat B searches base + its own uploads and must not see chat A's file.
        hits_b = vector_store.search("bluebird launch code", top_k=5,
                                     scopes=[BASE_SCOPE, "session-B"])
        assert all(h["source"] != "secret.txt" for h in hits_b)
    finally:
        vector_store.delete_scope("session-A")


def test_clearing_a_session_leaves_the_base_knowledge_base_intact():
    base_before = vector_store.count_for_scopes(BASE_ONLY)
    records = [{"chunk_id": "temp_1", "source": "temp.txt", "page": None,
                "text": "Temporary uploaded content for this chat only."}]
    vector_store.add_chunks(records, scope="session-C")
    assert vector_store.count_for_scopes(["session-C"]) == 1

    indexer.clear_session_uploads("session-C")

    assert vector_store.count_for_scopes(["session-C"]) == 0
    assert vector_store.count_for_scopes(BASE_ONLY) == base_before
