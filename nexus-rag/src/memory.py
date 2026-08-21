"""
Controlled conversation memory. Keeps only the last N turns so follow-up
questions ("what happens if I don't meet it?") resolve correctly, without
sending the entire chat history to the LLM on every request.
"""
from typing import List, Dict
from src.config import MAX_HISTORY_TURNS

# In-memory per-session store. Keyed by session_id (browser tab / user).
_sessions: Dict[str, List[Dict]] = {}


def get_history(session_id: str) -> List[Dict]:
    return _sessions.get(session_id, [])


def add_turn(session_id: str, question: str, answer: str):
    history = _sessions.setdefault(session_id, [])
    history.append({"question": question, "answer": answer})
    if len(history) > MAX_HISTORY_TURNS:
        del history[0: len(history) - MAX_HISTORY_TURNS]


def clear_history(session_id: str):
    _sessions.pop(session_id, None)


def last_question(session_id: str) -> str:
    """Most recent user question, used to give follow-ups enough context to retrieve."""
    history = get_history(session_id)
    return history[-1]["question"] if history else ""


def format_history_for_prompt(session_id: str) -> str:
    """Compact text block of recent turns, for the LLM to resolve pronouns/follow-ups."""
    history = get_history(session_id)
    if not history:
        return ""
    lines = []
    for turn in history:
        lines.append(f"User: {turn['question']}")
        lines.append(f"Assistant: {turn['answer']}")
    return "\n".join(lines)
