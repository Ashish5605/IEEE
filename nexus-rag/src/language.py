"""
Language detection, labels, and localized fixed responses for
English / Tamil / Hindi.

Detection is script-based: Tamil and Hindi use distinct Unicode blocks, so a
question written in either script is identified reliably without an extra
dependency or a model call. Anything else falls back to English.
"""
import re
from src.config import SUPPORTED_LANGUAGES

# Unicode ranges: Tamil U+0B80-U+0BFF, Devanagari (Hindi) U+0900-U+097F
_TAMIL_RE = re.compile(r"[\u0B80-\u0BFF]")
_HINDI_RE = re.compile(r"[\u0900-\u097F]")

DEFAULT_LANGUAGE = "en"

# Shown when retrieval finds nothing above the relevance threshold. Returned
# directly without an LLM call, so it has to be pre-translated.
NOT_FOUND_MESSAGES = {
    "en": "I couldn't find sufficient information about this in the provided knowledge base.",
    "ta": "வழங்கப்பட்ட அறிவுத் தளத்தில் இதைப் பற்றிய போதுமான தகவல் இல்லை.",
    "hi": "प्रदान किए गए ज्ञान आधार में इसके बारे में पर्याप्त जानकारी नहीं मिली।",
}

# Reply to a bare greeting. Also returned without an LLM call.
GREETING_RESPONSES = {
    "en": "Hi! Ask me anything about the documents in your knowledge base.",
    "ta": "வணக்கம்! உங்கள் அறிவுத் தளத்தில் உள்ள ஆவணங்களைப் பற்றி எதையும் கேளுங்கள்.",
    "hi": "नमस्ते! अपने ज्ञान आधार के दस्तावेज़ों के बारे में कुछ भी पूछें।",
}


# Shown when the user asks what the assistant knows, rather than asking a question
# the documents can answer. Followed by the actual document list.
CORPUS_INTRO = {
    "en": "I can answer questions about these documents:",
    "ta": "இந்த ஆவணங்களைப் பற்றிய கேள்விகளுக்கு என்னால் பதிலளிக்க முடியும்:",
    "hi": "मैं इन दस्तावेज़ों के बारे में सवालों के जवाब दे सकता हूँ:",
}

CORPUS_EMPTY = {
    "en": "There are no documents in the knowledge base yet. Upload one to get started.",
    "ta": "அறிவுத் தளத்தில் இன்னும் ஆவணங்கள் இல்லை. தொடங்க ஒன்றைப் பதிவேற்றவும்.",
    "hi": "ज्ञान आधार में अभी कोई दस्तावेज़ नहीं है। शुरू करने के लिए एक अपलोड करें।",
}


def detect_language(text: str) -> str:
    """Best-effort script-based detection. Falls back to English."""
    if _TAMIL_RE.search(text or ""):
        return "ta"
    if _HINDI_RE.search(text or ""):
        return "hi"
    return DEFAULT_LANGUAGE


def resolve_language(requested: str, question: str) -> str:
    """
    Decide which language to answer in.

    The UI sends "auto" by default, which means "match the language the question
    was asked in". An explicit language choice from the selector wins over
    detection, so a user can type in English and still get a Tamil answer.
    Unknown values fall back to detection rather than erroring.
    """
    if requested and requested in SUPPORTED_LANGUAGES:
        return requested
    return detect_language(question)


def language_name(code: str) -> str:
    return SUPPORTED_LANGUAGES.get(code, SUPPORTED_LANGUAGES[DEFAULT_LANGUAGE])


def not_found_message(code: str) -> str:
    return NOT_FOUND_MESSAGES.get(code, NOT_FOUND_MESSAGES[DEFAULT_LANGUAGE])


def greeting_response(code: str) -> str:
    return GREETING_RESPONSES.get(code, GREETING_RESPONSES[DEFAULT_LANGUAGE])


def corpus_intro(code: str) -> str:
    return CORPUS_INTRO.get(code, CORPUS_INTRO[DEFAULT_LANGUAGE])


def corpus_empty(code: str) -> str:
    return CORPUS_EMPTY.get(code, CORPUS_EMPTY[DEFAULT_LANGUAGE])
