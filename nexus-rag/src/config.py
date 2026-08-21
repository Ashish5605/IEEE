"""
Central configuration for Nexora.
Every tunable value lives here — nothing is hardcoded elsewhere in the app.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(BASE_DIR, "data", "documents")
VECTOR_DIR = os.path.join(BASE_DIR, "vectorstore")

# --- LLM ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")  # gemini | groq | openai | ollama
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.0-flash")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# --- Embeddings ---
# Multilingual model — required for English/Tamil/Hindi cross-language retrieval.
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-mpnet-base-v2")

# --- Chunking ---
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))       # tokens (approx, word-based)
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))  # tokens

# --- Retrieval ---
TOP_K = int(os.getenv("TOP_K", "5"))
RELEVANCE_THRESHOLD = float(os.getenv("RELEVANCE_THRESHOLD", "0.35"))  # cosine similarity floor

# --- Conversation memory ---
MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "4"))  # last N Q&A pairs kept in context

# --- Languages ---
SUPPORTED_LANGUAGES = {
    "en": "English",
    "ta": "Tamil",
    "hi": "Hindi",
}

# --- Collection name for vector store ---
COLLECTION_NAME = "nexora_knowledge_base"
