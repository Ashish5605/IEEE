"""
Central configuration for Nexora.
Every tunable value lives here — nothing is hardcoded elsewhere in the app.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

# The fixed, provided knowledge base. These documents ship with the project,
# are indexed automatically on first startup, and are available in every chat.
BASE_DOCS_DIR = os.path.join(DATA_DIR, "documents")

# Per-chat uploads. Temporary: scoped to one chat session and deleted when that
# chat is cleared or replaced. Kept in a separate tree so clearing a chat can
# never touch the provided knowledge base above.
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")

VECTOR_DIR = os.path.join(BASE_DIR, "vectorstore")

# Metadata scope tag used for the permanent, shared knowledge base. Per-chat
# uploads are tagged with their session_id instead.
BASE_SCOPE = "__base__"

# Nexora answers questions about a fixed set of college policy documents. User
# uploads are disabled so the corpus stays authoritative and every answer is
# traceable to an official document. Flip to True to restore per-chat uploads —
# the scope machinery behind them is intact.
UPLOADS_ENABLED = os.getenv("UPLOADS_ENABLED", "0") == "1"

# --- LLM ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")  # gemini | groq | xai | openai | ollama
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.0-flash")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# Optional override for any OpenAI-compatible endpoint (xAI, OpenRouter, Together,
# a local vLLM server). Leave empty to use the provider's default.
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")

# --- Embeddings ---
# Sentence embedding model, run locally. The checkpoint name carries
# "multilingual" but the assistant answers in English only; it is used here
# simply as a strong general-purpose sentence encoder.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-mpnet-base-v2")

# --- Chunking ---
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "250"))       # words per chunk
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "60"))  # words repeated between chunks

# --- Retrieval ---
TOP_K = int(os.getenv("TOP_K", "5"))
RELEVANCE_THRESHOLD = float(os.getenv("RELEVANCE_THRESHOLD", "0.35"))  # cosine similarity floor

# Below this, a question isn't merely uncovered by the documents — it is about
# something else entirely, and the user is told so explicitly rather than given
# a bare "not found". Measured against the corpus: clearly off-topic questions
# score 0.09-0.17, while in-domain questions start around 0.28.
SCOPE_FLOOR = float(os.getenv("SCOPE_FLOOR", "0.22"))

# --- Conversation memory ---
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "4"))  # last N Q&A pairs kept in context

# --- Language ---
SUPPORTED_LANGUAGES = {
    "en": "English",
}

# --- Collection name for vector store ---
COLLECTION_NAME = "nexora_knowledge_base"
