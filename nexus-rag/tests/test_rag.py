"""
End-to-end RAG tests. Requires LLM_API_KEY to be set for full pipeline tests;
retrieval-only assertions run regardless.
Run with: pytest tests/test_rag.py
"""
import pytest
from src import indexer, config, language
from src.rag_pipeline import answer_question, _is_pure_greeting


def setup_module(module):
    indexer.ensure_base_index()


def test_missing_information_response_without_llm_call():
    # Set an impossibly high threshold so nothing passes -> hallucination guard triggers
    result = answer_question(
        "What is the population of Japan?",
        session_id="test-session-1",
        threshold=0.99,
    )
    assert result["grounded"] is False
    assert result["answer"] == language.not_found_message("en")


def test_missing_information_response_is_localized():
    """The not-found guard must answer in the question's language, not always English."""
    result = answer_question(
        "ஜப்பானின் மக்கள்தொகை என்ன?",
        session_id="test-session-ta",
        threshold=0.99,
    )
    assert result["grounded"] is False
    assert result["language"] == "ta"
    assert result["answer"] == language.not_found_message("ta")


def test_explicit_language_selection_is_honoured():
    result = answer_question(
        "What is the population of Japan?",
        session_id="test-session-hi",
        requested_language="hi",
        threshold=0.99,
    )
    assert result["language"] == "hi"
    assert result["answer"] == language.not_found_message("hi")


def test_greeting_short_circuits_without_llm_call():
    result = answer_question("hello", session_id="test-session-greet")
    assert result["answer"] == language.greeting_response("en")
    assert result["sources"] == []


def test_greeting_detection_survives_indic_combining_marks():
    # Combining marks are not isalnum(); stripping them would mangle these words.
    assert _is_pure_greeting("வணக்கம்")
    assert _is_pure_greeting("नमस्ते")
    assert not _is_pure_greeting("What is the attendance policy?")


def test_localized_greeting_response():
    result = answer_question("வணக்கம்", session_id="test-session-greet-ta")
    assert result["language"] == "ta"
    assert result["answer"] == language.greeting_response("ta")


@pytest.mark.skipif(not config.LLM_API_KEY, reason="Requires LLM_API_KEY to be set")
def test_grounded_answer_with_llm():
    result = answer_question("What is the minimum attendance requirement?",
                             session_id="test-session-2")
    assert "error" not in result
    assert result["grounded"] is True
    assert len(result["answer"]) > 0
    assert len(result["sources"]) > 0


def test_followup_question_retrieves_via_conversation_context():
    """
    A pronoun-only follow-up has no topical content of its own, so retrieval on
    the bare string finds nothing. It must inherit context from the prior turn.
    """
    from src import retriever, memory
    from src.config import BASE_SCOPE

    session = "test-followup"
    memory.clear_history(session)

    followup = "What happens if I do not meet it?"
    # Bare retrieval genuinely fails -- this is what makes the fallback necessary.
    bare = retriever.retrieve(followup, scopes=[BASE_SCOPE])
    assert bare["grounded"] is False

    # With a prior turn in memory, the pipeline should still ground the answer.
    memory.add_turn(session, "What is the minimum attendance requirement?",
                    "The minimum attendance requirement is 75%.")
    result = answer_question(followup, session_id=session)
    assert result.get("grounded") is True, "follow-up should inherit prior context"
    assert len(result.get("sources", [])) > 0


def test_topic_change_is_not_polluted_by_prior_turn():
    """The context fallback must not drag an unrelated prior question into scope."""
    from src import memory
    session = "test-topic-change"
    memory.clear_history(session)
    memory.add_turn(session, "What is the minimum attendance requirement?",
                    "The minimum attendance requirement is 75%.")
    result = answer_question("What is the population of Japan?", session_id=session)
    assert result["grounded"] is False


def test_corpus_question_lists_documents_without_retrieval():
    """
    "What do you know?" is about the corpus, not answerable from it — every chunk
    embeds far away, so retrieval finds nothing and the user hits a dead end.
    It must be answered from the index instead.
    """
    from src import retriever
    from src.config import BASE_SCOPE
    from src.rag_pipeline import _is_corpus_question

    assert retriever.retrieve("What do you know?", scopes=[BASE_SCOPE])["grounded"] is False
    assert _is_corpus_question("What do you know?")

    result = answer_question("What do you know?", session_id="test-corpus")
    assert result["grounded"] is True
    # The corpus is the eight official Northbridge policy documents.
    assert "NB-AR-01" in result["answer"]
    assert result["answer"].count("- NB-") == 8


def test_corpus_question_detection_is_multilingual_without_false_positives():
    from src.rag_pipeline import _is_corpus_question as f
    assert f("நீங்கள் என்ன ஆவணங்கள் வைத்திருக்கிறீர்கள்?")
    assert f("आपके पास कौन से दस्तावेज़ हैं?")
    # Real content questions must still go to retrieval.
    assert not f("குறைந்தபட்ச வருகைத் தேவை என்ன?")
    assert not f("न्यूनतम उपस्थिति की आवश्यकता क्या है?")
    assert not f("What is the minimum attendance requirement?")


def test_ungrounded_result_marks_its_candidates_as_rejected():
    """
    The map must not paint rejected candidates as retrieved hits — that would
    show a constellation implying a grounded answer the text denies.
    """
    result = answer_question("What is the population of Japan?", session_id="test-nearmiss")
    assert result["grounded"] is False
    assert result.get("grounded_ids") is False


def test_empty_question_is_rejected():
    result = answer_question("", session_id="test-session-3")
    assert "error" in result
