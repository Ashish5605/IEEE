"""
Language handling. Nexora answers in English only.

The fixed responses live here rather than inline so the assistant's wording is
defined in one place, and so the module keeps a stable seam if further languages
are ever added back.
"""
from src.config import SUPPORTED_LANGUAGES

DEFAULT_LANGUAGE = "en"

NOT_FOUND_MESSAGES = {
    "en": "I couldn't find sufficient information about this in the provided knowledge base.",
}

GREETING_RESPONSES = {
    "en": "Hi! Ask me anything about the documents in your knowledge base.",
}

CORPUS_INTRO = {
    "en": "I can answer questions about these documents:",
}

CORPUS_EMPTY = {
    "en": "There are no documents in the knowledge base yet.",
}

# Shown when a question is not about the institution at all. Distinct from the
# not-found message: that one means "the documents don't cover this", whereas
# this one means "this is not what I am for".
OUT_OF_SCOPE = {
    "en": (
        "I can only answer questions about Northbridge Institute of Technology's "
        "official policy documents — academics, examinations, attendance, "
        "internships, library, scholarships, placements and student conduct.\n\n"
        "That question falls outside those documents, so I won't attempt an answer."
    ),
}


def detect_language(text: str) -> str:
    """Kept as a seam; the assistant is English-only."""
    return DEFAULT_LANGUAGE


def resolve_language(requested: str, question: str) -> str:
    """Answers are always produced in English."""
    return DEFAULT_LANGUAGE


def language_name(code: str) -> str:
    return SUPPORTED_LANGUAGES.get(code, SUPPORTED_LANGUAGES[DEFAULT_LANGUAGE])


def not_found_message(code: str = DEFAULT_LANGUAGE) -> str:
    return NOT_FOUND_MESSAGES[DEFAULT_LANGUAGE]


def greeting_response(code: str = DEFAULT_LANGUAGE) -> str:
    return GREETING_RESPONSES[DEFAULT_LANGUAGE]


def corpus_intro(code: str = DEFAULT_LANGUAGE) -> str:
    return CORPUS_INTRO[DEFAULT_LANGUAGE]


def corpus_empty(code: str = DEFAULT_LANGUAGE) -> str:
    return CORPUS_EMPTY[DEFAULT_LANGUAGE]


def out_of_scope_message(code: str = DEFAULT_LANGUAGE) -> str:
    return OUT_OF_SCOPE[DEFAULT_LANGUAGE]
