"""
Abusive-language guard.

Three escalating responses: a warning, a final warning, then a 24-hour block.
State is per chat session and persisted to disk so a server restart does not
quietly forgive a ban.

Matching is deliberately conservative. Substring matching on profanity is a
well-known trap — it flags "class", "assignment", "Scunthorpe" and similar
ordinary words, which in a college policy assistant would be a constant
irritation. Words are matched on boundaries only, after normalising the common
character substitutions used to slip past filters.
"""
import json
import os
import re
import time
from typing import Dict, Optional

from src.config import BASE_DIR

MODERATION_PATH = os.path.join(BASE_DIR, "data", "moderation.json")

STRIKES_BEFORE_BAN = 3
BAN_SECONDS = 24 * 60 * 60

# Base forms only; the matcher handles plurals and common suffixes.
_PROFANITY = {
    "fuck", "fucker", "fucking", "motherfucker", "shit", "bullshit", "bitch",
    "bastard", "asshole", "arsehole", "dickhead", "prick", "cunt", "slut",
    "whore", "wanker", "twat", "retard", "faggot", "nigger", "nigga",
}

# Leet substitutions, so "f*ck" / "sh1t" / "@sshole" still register.
_LEET = str.maketrans({"@": "a", "4": "a", "3": "e", "1": "i", "!": "i",
                       "0": "o", "5": "s", "$": "s", "7": "t"})

# Masking characters stand in for letters ("f**k", "sh##t"). Each run becomes a
# wildcard so the word is matched by shape rather than by exact spelling.
_MASK_RE = re.compile(r"[*#%&]+")

_WORD_RE = re.compile(r"[a-z]+")

# Censored spellings ("f*ck", "sh!t") lose their vowels once the punctuation is
# stripped, so also match each profanity with its vowels removed.
_DEVOWELLED = {re.sub(r"[aeiou]", "", w) for w in _PROFANITY if len(re.sub(r"[aeiou]", "", w)) >= 2}


def _normalise(text: str) -> str:
    return (text or "").lower().translate(_LEET)


def _masked_hit(raw_word: str) -> bool:
    """Match a masked word like "f**k" against the profanity list by shape."""
    if not _MASK_RE.search(raw_word):
        return False
    pattern = _MASK_RE.sub(lambda m: "." + "{1,%d}" % (len(m.group()) + 1), raw_word.lower())
    try:
        rx = re.compile(r"^" + pattern + r"$")
    except re.error:
        return False
    return any(rx.match(w) for w in _PROFANITY)


def contains_abuse(text: str) -> bool:
    """
    True when a profanity appears as its own word.

    Word-boundary matching is the whole point: "assignment" and "classification"
    must never trip this, and they do under naive substring search.
    """
    # Masked words are checked on the raw text, before punctuation is stripped.
    for raw in re.findall(r"[A-Za-z*#%&]{2,}", text or ""):
        if _masked_hit(raw):
            return True

    words = _WORD_RE.findall(_normalise(text))
    for w in words:
        if w in _PROFANITY:
            return True
        if w in _DEVOWELLED:
            return True
        # Strip a trailing plural / -ing / -ed so "bitches" or "fucked" match.
        for suffix in ("es", "s", "ing", "ed", "er"):
            if w.endswith(suffix) and w[: -len(suffix)] in _PROFANITY:
                return True
    return False


# ---- persistence -----------------------------------------------------------

def _load() -> Dict:
    try:
        with open(MODERATION_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save(state: Dict) -> None:
    os.makedirs(os.path.dirname(MODERATION_PATH), exist_ok=True)
    with open(MODERATION_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _record(session_id: str) -> Dict:
    return _load().get(session_id, {"strikes": 0, "banned_until": 0})


# ---- public API ------------------------------------------------------------

def ban_remaining(session_id: str) -> int:
    """Seconds left on an active ban, or 0."""
    rec = _record(session_id)
    return max(0, int(rec.get("banned_until", 0) - time.time()))


def is_banned(session_id: str) -> bool:
    return ban_remaining(session_id) > 0


def register_strike(session_id: str) -> Dict:
    """
    Count one offence. Returns {strikes, banned, remaining}.
    The third strike starts the 24-hour block.
    """
    state = _load()
    rec = state.get(session_id, {"strikes": 0, "banned_until": 0})
    rec["strikes"] = int(rec.get("strikes", 0)) + 1
    if rec["strikes"] >= STRIKES_BEFORE_BAN:
        rec["banned_until"] = time.time() + BAN_SECONDS
    state[session_id] = rec
    _save(state)
    return {
        "strikes": rec["strikes"],
        "banned": rec["strikes"] >= STRIKES_BEFORE_BAN,
        "remaining": max(0, int(rec.get("banned_until", 0) - time.time())),
    }


def clear(session_id: str) -> None:
    """Lift a ban and reset strikes. Used by tests and by an operator."""
    state = _load()
    state.pop(session_id, None)
    _save(state)


def format_duration(seconds: int) -> str:
    hours, rem = divmod(max(0, seconds), 3600)
    minutes = rem // 60
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def warning_message(strikes: int, banned: bool, remaining: int) -> str:
    if banned:
        return (
            f"**Access blocked for {format_duration(remaining)}.**\n\n"
            f"This assistant has recorded {strikes} instances of abusive language. "
            "Access to the knowledge base is suspended for 24 hours."
        )
    left = STRIKES_BEFORE_BAN - strikes
    tail = ("This is your final warning — one more will suspend access for 24 hours."
            if left == 1 else
            f"{left} further instances will suspend access for 24 hours.")
    return (
        f"**Please keep it civil.** (Warning {strikes} of {STRIKES_BEFORE_BAN})\n\n"
        f"This assistant answers questions about Northbridge policy documents. {tail}"
    )


def ban_message(remaining: int) -> str:
    return (
        f"**Access blocked.** Try again in {format_duration(remaining)}.\n\n"
        "Access was suspended after repeated abusive language."
    )
