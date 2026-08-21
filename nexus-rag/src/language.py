"""
Language detection and label helpers for English / Tamil / Hindi.
"""
import re
from src.config import SUPPORTED_LANGUAGES

# Unicode ranges: Tamil U+0B80–U+0BFF, Devanagari (Hindi) U+0900–U+097F
_TAMIL_RE = re.compile(r"[\u0B80-\u0BFF]")
_HINDI_RE = re.compile(r"[\u0900-\u097F]")


def detect_language(text: str) -> str:
    """Best-effort script-based detection. Falls back to English."""
    if _TAMIL_RE.search(text):
        return "ta"
    if _HINDI_RE.search(text):
        return "hi"
    return "en"


def language_name(code: str) -> str:
    return SUPPORTED_LANGUAGES.get(code, "English")
