"""
Orchestrates the full RAG pipeline: retrieve -> filter -> prompt -> LLM -> response.
This is the single entry point the Flask app calls.
"""
import os
from src import retriever, llm, citations, memory
from src.config import BASE_DIR, TOP_K, RELEVANCE_THRESHOLD

_PROMPT_PATH = os.path.join(BASE_DIR, "prompts", "rag_prompt.txt")
with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
    _PROMPT_TEMPLATE = f.read()

NOT_FOUND_MESSAGE = "I couldn't find sufficient information about this in the provided knowledge base."

# Simple conversational messages that should never trigger document retrieval
# or an LLM call — matched on exact/near-exact cleaned text, not substring,
# so this never swallows a real question that happens to start with "hi".
GREETING_RESPONSE = "Hi! Ask me anything about the documents in your knowledge base."

_GREETING_PATTERNS = {
    "hi", "hello", "hey", "hii", "hiii", "yo", "good morning", "good afternoon",
    "good evening", "how are you", "whats up", "what's up", "sup", "hola",
}


def _clean_for_match(text: str) -> str:
    return "".join(c for c in text.lower().strip() if c.isalnum() or c.isspace()).strip()


def _is_pure_greeting(question: str) -> bool:
    """True only for short, exact greeting-style messages — not substrings inside a real question."""
    cleaned = _clean_for_match(question)
    if not cleaned or len(cleaned.split()) > 4:
        return False
    return cleaned in _GREETING_PATTERNS


def _format_context(chunks):
    if not chunks:
        return "(no relevant context retrieved)"
    lines = []
    for c in chunks:
        page_str = f", page {c['page']}" if c["page"] else ""
        lines.append(f"[Source: {c['source']}{page_str}]\n{c['text']}")
    return "\n\n".join(lines)


def answer_question(question: str, session_id: str,
                     source_filter: str = None, top_k: int = TOP_K,
                     threshold: float = RELEVANCE_THRESHOLD) -> dict:
    """
    Returns a dict ready to be JSON-serialized to the frontend:
    {
      answer, language, grounded, sources, evidence, error
    }
    """
    question = (question or "").strip()
    if not question:
        return {"error": "Please enter a question."}

    # 0. Fast path: pure greetings never touch retrieval or the LLM.
    if _is_pure_greeting(question):
        memory.add_turn(session_id, question, GREETING_RESPONSE)
        return {
            "answer": GREETING_RESPONSE,
            "language": "en",
            "grounded": True,
            "sources": [],
            "evidence": [],
        }

    # 1. Retrieve
    result = retriever.retrieve(question, session_id=session_id, top_k=top_k, threshold=threshold, source_filter=source_filter)

    if not result["grounded"]:
        memory.add_turn(session_id, question, NOT_FOUND_MESSAGE)
        return {
            "answer": NOT_FOUND_MESSAGE,
            "language": "en",
            "grounded": False,
            "sources": [],
            "evidence": citations.build_evidence(result["all_candidates"]),
        }

    # 2. Build prompt
    context_str = _format_context(result["chunks"])
    history_str = memory.format_history_for_prompt(session_id) or "(no prior turns)"
    prompt = _PROMPT_TEMPLATE.format(
        language_name="English",
        history=history_str,
        context=context_str,
        question=question,
    )

    # 3. Call LLM
    try:
        answer_text = llm.generate(system_prompt="You are Nexora, a grounded knowledge assistant.",
                                    user_prompt=prompt)
    except llm.LLMError as e:
        return {"error": str(e)}

    if not answer_text:
        answer_text = NOT_FOUND_MESSAGE

    # 4. Save memory + build citations
    memory.add_turn(session_id, question, answer_text)

    return {
        "answer": answer_text,
        "language": "en",
        "grounded": True,
        "sources": citations.build_sources(result["chunks"]),
        "evidence": citations.build_evidence(result["chunks"]),
    }
