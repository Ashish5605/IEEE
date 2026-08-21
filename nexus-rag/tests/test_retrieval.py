"""
Retrieval tests. Run with: pytest tests/test_retrieval.py
Requires the index to be built first (python -c "from src.indexer import build_index; build_index()")
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import retriever, indexer


def setup_module(module):
    indexer.build_index(force=False)


def test_relevant_question_returns_grounded_result():
    result = retriever.retrieve("What is the minimum attendance requirement?")
    assert result["grounded"] is True
    assert len(result["chunks"]) > 0


def test_irrelevant_question_is_not_grounded():
    result = retriever.retrieve("What is the population of Japan?", threshold=0.6)
    # Should either be empty or below threshold — never confidently grounded on unrelated content
    assert result["grounded"] is False or all(c["score"] < 0.6 for c in result["all_candidates"])


def test_cross_language_question_still_retrieves_english_chunk():
    # Tamil phrasing of an attendance question should still hit the English source chunk
    result = retriever.retrieve("குறைந்தபட்ச வருகைத் தேவை என்ன?", threshold=0.2)
    assert len(result["all_candidates"]) > 0


def test_document_filter_restricts_results():
    docs = retriever.vector_store.search("attendance", top_k=5)
    if docs:
        source = docs[0]["source"]
        filtered = retriever.retrieve("attendance", source_filter=source)
        assert all(c["source"] == source for c in filtered["chunks"])
