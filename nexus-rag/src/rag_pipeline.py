"""
Orchestrates the full RAG pipeline: retrieve -> filter -> prompt -> LLM -> response.
This is the single entry point the Flask app calls.

Answers are returned in English. The fixed responses (greeting, nothing-found,
corpus listing) live in src/language.py and are returned without an LLM call.
"""
import os
import unicodedata
from src import retriever, llm, citations, memory, indexer, language, semantic_map, vector_store
from src.config import BASE_DIR, TOP_K, RELEVANCE_THRESHOLD, SCOPE_FLOOR

_PROMPT_PATH = os.path.join(BASE_DIR, "prompts", "rag_prompt.txt")
with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
    _PROMPT_TEMPLATE = f.read()

# Simple conversational messages that should never trigger document retrieval
# or an LLM call — matched on exact/near-exact cleaned text, not substring,
# so this never swallows a real question that happens to start with "hi".
_GREETING_PATTERNS = {
    "hi", "hello", "hey", "hii", "hiii", "yo", "good morning", "good afternoon",
    "good evening", "how are you", "whats up", "what's up", "sup", "hola",
}


def _keep_for_match(c: str) -> bool:
    # Combining marks (category M*) are not alphanumeric, so an isalnum()-only
    # filter would silently drop accents and diacritics from a greeting.
    return c.isalnum() or c.isspace() or unicodedata.category(c).startswith("M")


def _clean_for_match(text: str) -> str:
    return "".join(c for c in text.lower().strip() if _keep_for_match(c)).strip()


def _is_pure_greeting(question: str) -> bool:
    """True only for short, exact greeting-style messages — not substrings inside a real question."""
    cleaned = _clean_for_match(question)
    if not cleaned or len(cleaned.split()) > 4:
        return False
    return cleaned in _GREETING_PATTERNS


# Words that make a question depend on what came before it. Without one of these
# a question stands on its own, and borrowing prior context would only drag an
# unrelated topic into retrieval.
_REFERRING_TOKENS = {
    "it", "its", "it's", "that", "this", "these", "those", "they", "them",
    "their", "he", "she", "him", "her", "one", "same", "there",
}


def _is_context_dependent(question: str) -> bool:
    """
    True when the question cannot be understood alone — e.g. "what happens if I
    don't meet it?". Only these inherit context from the previous turn.
    """
    words = _clean_for_match(question).split()
    if not words:
        return False
    return any(w in _REFERRING_TOKENS for w in words)


# "What do you know?" is a question about the corpus, not a question the corpus
# can answer — every chunk embeds far away from it, so retrieval correctly finds
# nothing and the user gets a dead end. Answer these from the index itself.
_CORPUS_QUESTIONS = (
    "what do you know", "what do u know", "what can you do", "what can you help",
    "what documents", "which documents", "what files", "which files",
    "what is in your knowledge base", "whats in your knowledge base",
    "what is in the knowledge base", "whats in the knowledge base",
    "list documents", "list the documents", "what do you have",
    "what topics", "what can i ask",
    "क्या दस्तावेज", "कौन सी फ़ाइलें",
)


def _is_corpus_question(question: str) -> bool:
    cleaned = _clean_for_match(question)
    return any(pat in cleaned for pat in _CORPUS_QUESTIONS)


def _corpus_answer(scopes, lang: str) -> str:
    sources = vector_store.sources_in_scopes(scopes)
    if not sources:
        return language.corpus_empty(lang)
    lines = [language.corpus_intro(lang), ""]
    lines += [f"- {s}" for s in sources]
    return "\n".join(lines)


def _format_context(chunks):
    if not chunks:
        return "(no relevant context retrieved)"
    lines = []
    for c in chunks:
        page_str = f", page {c['page']}" if c["page"] else ""
        lines.append(f"[Source: {c['source']}{page_str}]\n{c['text']}")
    return "\n\n".join(lines)


def answer_question(question: str, session_id: str, requested_language: str = "auto",
                    source_filter: str = None, top_k: int = TOP_K,
                    threshold: float = RELEVANCE_THRESHOLD) -> dict:
    """
    Returns a dict ready to be JSON-serialized to the frontend:
    {
      answer, language, grounded, sources, evidence, error
    }

    requested_language: "auto" (detect from the question) or an explicit
    supported code ("en" | "ta" | "hi") chosen in the UI.
    """
    question = (question or "").strip()
    if not question:
        return {"error": "Please enter a question."}

    lang = language.resolve_language(requested_language, question)

    # 0. Fast path: pure greetings never touch retrieval or the LLM.
    if _is_pure_greeting(question):
        greeting = language.greeting_response(lang)
        memory.add_turn(session_id, question, greeting)
        return {
            "answer": greeting,
            "language": lang,
            "grounded": True,
            "sources": [],
            "evidence": [],
            "retrieved_ids": [],
            "query_point": None,
        }

    scopes = indexer.scopes_for(session_id)

    # 0b. Questions about the knowledge base itself are answered from the index,
    # not by searching it. No LLM call needed.
    if _is_corpus_question(question):
        answer = _corpus_answer(scopes, lang)
        memory.add_turn(session_id, question, answer)
        return {
            "answer": answer, "language": lang, "grounded": True,
            "sources": [], "evidence": [], "retrieved_ids": [], "query_point": None,
        }

    # 1. Retrieve across the shared base knowledge base + this chat's uploads
    result = retriever.retrieve(
        question,
        scopes=scopes,
        top_k=top_k,
        threshold=threshold,
        source_filter=source_filter,
    )

    # A pronoun-only follow-up ("what happens if I don't meet it?") carries no
    # topical content of its own, so its embedding matches nothing and retrieval
    # fails before conversation memory — which only reaches the LLM prompt — can
    # help. When the bare query finds nothing and there is a prior turn, retry
    # with that turn prepended. Fallback-only, so a genuine change of subject is
    # never polluted by stale context.
    if not result["grounded"] and _is_context_dependent(question):
        prior = memory.last_question(session_id)
        if prior:
            contextual = retriever.retrieve(
                f"{prior} {question}", scopes=scopes, top_k=top_k,
                threshold=threshold, source_filter=source_filter,
            )
            if contextual["grounded"]:
                result = contextual

    # Scope guard. A question the corpus barely registers at all is not an
    # uncovered institutional question — it is a question about something else.
    # Say so plainly instead of implying the documents merely lack the detail.
    top_score = result["all_candidates"][0]["score"] if result["all_candidates"] else 0.0
    if not result["grounded"] and top_score < SCOPE_FLOOR:
        warning = language.out_of_scope_message(lang)
        memory.add_turn(session_id, question, warning)
        return {
            "answer": warning,
            "language": lang,
            "grounded": False,
            "out_of_scope": True,
            "sources": [],
            "evidence": [],
            "retrieved_ids": [],
            "query_point": None,
        }

    if not result["grounded"]:
        not_found = language.not_found_message(lang)
        memory.add_turn(session_id, question, not_found)
        return {
            "answer": not_found,
            "language": lang,
            "grounded": False,
            "sources": [],
            "evidence": citations.build_evidence(result["all_candidates"]),
            # These were considered and rejected, not retrieved. The map renders
            # them as near-misses so it never implies a grounded answer.
            "retrieved_ids": [c["id"] for c in result["all_candidates"]],
            "grounded_ids": False,
            "query_point": semantic_map.project_query(question, scopes),
        }

    # 2. Build prompt
    context_str = _format_context(result["chunks"])
    history_str = memory.format_history_for_prompt(session_id) or "(no prior turns)"
    prompt = _PROMPT_TEMPLATE.format(
        language_name=language.language_name(lang),
        history=history_str,
        context=context_str,
        question=question,
    )

    # 3. Call LLM
    try:
        answer_text = llm.generate(system_prompt="You are Nexora, a grounded knowledge assistant.",
                                    user_prompt=prompt)
    except llm.LLMError as e:
        # Retrieval already succeeded; only generation failed. Return the grounding
        # we have so the UI can still show sources, evidence and the map.
        return {
            "error": str(e),
            "sources": citations.build_sources(result["chunks"]),
            "evidence": citations.build_evidence(result["chunks"]),
            "retrieved_ids": [c["id"] for c in result["chunks"]],
            "query_point": semantic_map.project_query(question, scopes),
        }

    if not answer_text:
        answer_text = language.not_found_message(lang)

    # 4. Save memory + build citations
    memory.add_turn(session_id, question, answer_text)

    return {
        "answer": answer_text,
        "language": lang,
        "grounded": True,
        "sources": citations.build_sources(result["chunks"]),
        "evidence": citations.build_evidence(result["chunks"]),
        "retrieved_ids": [c["id"] for c in result["chunks"]],
        "query_point": semantic_map.project_query(question, scopes),
    }
