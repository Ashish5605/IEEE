"""
Romanised Tamil / Hindi keyword glossary.

The embedding model handles native script well, and mixed "Tanglish"/"Hinglish"
already retrieves correctly because English domain words anchor the sentence.
What fails is fully romanised native vocabulary — "upasthiti kitni zaroori hai"
scores 0.08 because those spellings appear nowhere in its training.

This maps a small set of romanised terms to the English word the documents
actually use. The mapping is appended to the *retrieval query only* — never
shown to the user and never sent as the question — so it widens recall without
changing what is asked or what is quoted back.
"""
import re

# romanised form -> the English term used in the policy documents
_GLOSSARY = {
    # Tamil
    "varugai": "attendance", "vagupu": "class", "sathaveetham": "percentage",
    "thervu": "examination", "mathippeedu": "assessment", "vidumurai": "leave",
    "nool": "book", "noolagam": "library", "kalvi": "academic",
    "udhaviththogai": "scholarship", "velaivaaippu": "placement",
    "ethana": "how many", "evlo": "how much", "eppadi": "how",
    # Hindi
    "upasthiti": "attendance", "hazri": "attendance", "kaksha": "class",
    "pariksha": "examination", "mulyankan": "assessment", "chhutti": "leave",
    "avkash": "leave", "pustakalay": "library", "kitab": "book",
    "chhatravriti": "scholarship", "shulk": "fee", "niyam": "rules",
    "anushasan": "conduct", "kitna": "how much", "kitni": "how much",
    "zaroori": "required", "chahiye": "required", "aavashyak": "required",
}

_WORD_RE = re.compile(r"[a-z]+")


def expand_query(question: str) -> str:
    """
    Return the question with English equivalents appended for any romanised
    terms found. Returns it unchanged when nothing matches, so English and
    native-script questions are completely unaffected.
    """
    words = _WORD_RE.findall((question or "").lower())
    hits = []
    for w in words:
        term = _GLOSSARY.get(w)
        if term and term not in hits:
            hits.append(term)
    if not hits:
        return question
    return f"{question} {' '.join(hits)}"
