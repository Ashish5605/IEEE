"""Abusive-language guard: matching, escalation, and the 24-hour block."""
import time

from src import moderation as m
from src.rag_pipeline import answer_question


def teardown_function():
    for sid in ("mod-a", "mod-b", "mod-c"):
        m.clear(sid)


def test_ordinary_college_questions_are_never_flagged():
    """
    Substring matching on profanity flags "class", "assignment", "Scunthorpe".
    In a college assistant that would fire constantly, so matching is on word
    boundaries and these must all pass.
    """
    for q in ["What is the class attendance policy?",
              "How do I submit my assignment?",
              "Tell me about classification of grades",
              "What is the passing mark?",
              "Bass fishing club rules",
              "Is there a book limit in the library?"]:
        assert not m.contains_abuse(q), q


def test_abuse_is_detected_including_evasions():
    for q in ["what the fuck is this", "this is shit", "you are a bitch",
              "sh1t policy", "@sshole", "f**k this", "bitches"]:
        assert m.contains_abuse(q), q


def test_three_strikes_triggers_a_24_hour_ban():
    sid = "mod-a"
    m.clear(sid)
    first = m.register_strike(sid)
    assert first["strikes"] == 1 and not first["banned"]
    second = m.register_strike(sid)
    assert second["strikes"] == 2 and not second["banned"]
    third = m.register_strike(sid)
    assert third["strikes"] == 3 and third["banned"]
    assert m.is_banned(sid)
    # Within a minute of a full day.
    assert 24 * 3600 - 60 <= m.ban_remaining(sid) <= 24 * 3600


def test_pipeline_warns_then_blocks():
    sid = "mod-b"
    m.clear(sid)
    for expected in (1, 2):
        r = answer_question("what the fuck", session_id=sid)
        assert r["warned"] is True
        assert r["strikes"] == expected
        assert r["blocked"] is False
    r = answer_question("what the fuck", session_id=sid)
    assert r["blocked"] is True


def test_a_ban_blocks_even_a_legitimate_question():
    """The ban must gate everything, not just further abuse."""
    sid = "mod-c"
    m.clear(sid)
    for _ in range(3):
        answer_question("this is shit", session_id=sid)
    r = answer_question("What is the minimum attendance requirement?", session_id=sid)
    assert r["blocked"] is True
    assert r["grounded"] is False
    assert r["sources"] == []


def test_ban_state_survives_a_restart():
    """State is on disk, so restarting the server must not forgive a ban."""
    sid = "mod-a"
    m.clear(sid)
    for _ in range(3):
        m.register_strike(sid)
    assert m.is_banned(sid)
    # A fresh read of the file is what a new process would do.
    assert m._record(sid)["banned_until"] > time.time()


def test_clear_lifts_a_ban():
    sid = "mod-a"
    for _ in range(3):
        m.register_strike(sid)
    assert m.is_banned(sid)
    m.clear(sid)
    assert not m.is_banned(sid)
