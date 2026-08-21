"""
Persistent chat history — separate from src/memory.py (which is the short,
controlled window sent to the LLM for follow-up resolution).

This module stores the FULL conversation per session to a JSON file on disk,
so switching sidebar tabs (Main Chat / RAG Settings / History) or restarting
the server never loses what the user already asked.
"""
import os
import json
import time
from typing import List, Dict
from src.config import BASE_DIR

HISTORY_DIR = os.path.join(BASE_DIR, "data", "chat_history")
os.makedirs(HISTORY_DIR, exist_ok=True)


def _path_for(session_id: str) -> str:
    safe_id = "".join(c for c in session_id if c.isalnum() or c == "-")
    return os.path.join(HISTORY_DIR, f"{safe_id}.json")


def load_session(session_id: str) -> List[Dict]:
    """Full chat transcript for this session: [{role, content, meta, ts}, ...]"""
    path = _path_for(session_id)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def append_message(session_id: str, role: str, content: str, meta: Dict = None):
    """role: 'user' | 'assistant'. meta holds sources/evidence/language for assistant turns."""
    transcript = load_session(session_id)
    transcript.append({
        "role": role,
        "content": content,
        "meta": meta or {},
        "ts": time.time(),
    })
    with open(_path_for(session_id), "w", encoding="utf-8") as f:
        json.dump(transcript, f, ensure_ascii=False, indent=2)


def clear_session(session_id: str):
    path = _path_for(session_id)
    if os.path.exists(path):
        os.remove(path)


def list_sessions() -> List[Dict]:
    """Summaries of all saved sessions, most recent first — for a 'History' sidebar list."""
    summaries = []
    if not os.path.isdir(HISTORY_DIR):
        return summaries
    for filename in os.listdir(HISTORY_DIR):
        if not filename.endswith(".json"):
            continue
        session_id = filename[:-5]
        transcript = load_session(session_id)
        if not transcript:
            continue
        first_user_msg = next((m["content"] for m in transcript if m["role"] == "user"), "New conversation")
        summaries.append({
            "session_id": session_id,
            "title": first_user_msg[:60],
            "message_count": len(transcript),
            "last_updated": transcript[-1]["ts"],
        })
    summaries.sort(key=lambda s: s["last_updated"], reverse=True)
    return summaries
