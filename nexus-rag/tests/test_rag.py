"""
End-to-end RAG tests. Requires LLM_API_KEY to be set for full pipeline tests;
retrieval-only assertions run regardless.
Run with: pytest tests/test_rag.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from src import indexer, config
from src.rag_pipeline import answer_question


def setup_module(module):
    indexer.build_index(force=False)


def test_missing_information_response_without_llm_call():
    # Set an impossibly high threshold so nothing passes -> hallucination guard triggers
    result = answer_question(
        "What is the population of Japan?",
        session_id="test-session-1",
        threshold=0.99,
    )
    assert result["grounded"] is False
    assert "not" in result["answer"].lower() or "couldn't" in result["answer"].lower() or "இல்லை" in result["answer"] or "नहीं" in result["answer"]


@pytest.mark.skipif(not config.LLM_API_KEY, reason="Requires LLM_API_KEY to be set")
def test_grounded_answer_with_llm():
    result = answer_question("What is the minimum attendance requirement?", session_id="test-session-2")
    assert "error" not in result
    assert result["grounded"] is True
    assert len(result["answer"]) > 0
    assert len(result["sources"]) > 0


def test_empty_question_is_rejected():
    result = answer_question("", session_id="test-session-3")
    assert "error" in result
