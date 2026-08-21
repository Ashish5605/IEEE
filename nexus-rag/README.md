# Nexora — Multilingual Voice Knowledge Assistant

A multilingual (English / Tamil / Hindi), voice-enabled, source-grounded RAG knowledge assistant, built for IEEE Club Round 2.

## Problem statement

Users struggle to quickly find information buried in large document collections (handbooks, regulations, guidelines). Nexora lets them ask natural-language questions — by typing or speaking, in any of three languages — and get grounded answers backed by cited sources, not guesses.

## Objective

Build a Retrieval-Augmented Generation system that retrieves relevant passages from a fixed knowledge base and passes them to an LLM to generate an answer, with full source traceability and no hallucination.

## Features

- Multilingual retrieval — ask in English, Tamil, or Hindi even though source documents are in English (cross-language semantic search)
- Voice input via the browser's built-in speech recognition (Chrome), with language selection
- Text-to-speech playback of answers
- Source citations with document name + page number
- Expandable "View evidence" showing the actual retrieved passages and relevance scores
- Hallucination protection — if retrieved context doesn't clear the relevance threshold, the assistant says so instead of guessing
- Conversation memory for follow-up questions ("what happens if I don't meet it?")
- Document-scoped search (search all documents, or restrict to one)
- Configurable retrieval top-K and relevance threshold from the UI (advanced settings)
- Persistent vector storage — documents are embedded once, not on every question

## Architecture

```
 Documents (PDF/TXT/DOCX)
        |
        v
 Document ingestion (src/document_loader.py)
        |
        v
 Chunking, sentence-aware with overlap (src/chunker.py)
        |
        v
 Multilingual embeddings (src/embeddings.py)
        |
        v
 ChromaDB persistent vector store (src/vector_store.py)
        |
 -------+------- (question comes in here)
        |
        v
 Query embedding + vector search (src/retriever.py)
        |
        v
 Relevance threshold filter
        |
   +----+----+
   |         |
 below     above
 threshold threshold
   |         |
   v         v
"Not found"  Grounded prompt -> LLM (src/llm.py) -> answer
   |         |
   +----+----+
        |
        v
 Citations + evidence (src/citations.py)
        |
        v
 Flask API (app.py) -> Frontend (templates/index.html + static/js/app.js)
```

## Technology stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Flask | Lightweight, easy to demo and explain |
| Embeddings | `paraphrase-multilingual-mpnet-base-v2` (sentence-transformers) | Free, runs locally, genuinely multilingual — enables cross-language retrieval |
| Vector DB | ChromaDB | Free, persistent, built-in metadata filtering for document selection |
| LLM | Gemini (default, swappable to Groq/OpenAI/Ollama) | Free tier, strong at Indian languages |
| Voice input | Browser Web Speech API | Free, no server audio needed, supports en-IN/hi-IN/ta-IN |
| Text-to-speech | Browser SpeechSynthesis API | Free, works offline in-browser |
| Frontend | HTML/Tailwind (from Stitch export) + vanilla JS | Matches the designed UI exactly, no build step |

## Installation

```bash
git clone <your-repo>
cd nexus-rag
pip install -r requirements.txt
```

## Environment setup

```bash
cp .env.example .env
```

Then edit `.env` and add your free Gemini API key from https://aistudio.google.com/apikey (takes 2 minutes, no credit card).

To use a different provider instead, change `LLM_PROVIDER` in `.env` to `groq`, `openai`, or `ollama` and set the matching key/model.

## Knowledge base setup

Place your official Round 2 documents (`.pdf`, `.txt`, or `.docx`) in:

```
data/documents/
```

A placeholder sample document is included there so you can test the pipeline immediately — replace it with the real documents before your demo.

## Indexing

The app automatically indexes the knowledge base on first startup if it hasn't been indexed yet. To force a full rebuild (e.g. after adding new documents), either:

- Click **Rebuild knowledge base** in the sidebar, or
- Run: `python -c "from src.indexer import build_index; build_index(force=True)"`

The first run downloads the multilingual embedding model (~1GB, one-time, requires internet).

## Running

```bash
python app.py
```

Then open http://localhost:5000

## Example questions

- English: *What is the minimum attendance requirement?*
- Tamil: *குறைந்தபட்ச வருகைத் தேவை என்ன?*
- Hindi: *न्यूनतम उपस्थिति की आवश्यकता क्या है?*
- Follow-up: *What happens if I don't meet it?*
- Unsupported: *What is the population of Japan?* → returns "not found in knowledge base" instead of guessing

## How retrieval works

Every document is split into overlapping chunks (default ~800 words, ~150-word overlap) that preserve source filename and page number. Each chunk is embedded with a multilingual model and stored in ChromaDB. When a question comes in — in any supported language — it's embedded with the same model and compared against all stored chunks by cosine similarity. Because the embedding model is multilingual, a Tamil question and its semantically equivalent English sentence land close together in vector space, so the correct English chunk is retrieved even though the question wasn't in English.

## Hallucination protection

Retrieved chunks below `RELEVANCE_THRESHOLD` (default 0.35, adjustable in the sidebar) are discarded before the LLM ever sees them. If nothing clears the bar, the app returns a fixed "not found in knowledge base" message in the user's language without calling the LLM at all — so an ungrounded answer is structurally impossible, not just prompted against.

## Limitations

- Speech recognition accuracy for Tamil and Hindi depends on the browser's built-in engine and can vary with accent/microphone quality
- Answer quality depends entirely on the connected LLM provider and the quality/coverage of the source documents
- Cross-language retrieval quality depends on the multilingual embedding model — very short or ambiguous queries retrieve less reliably
- Web Speech API voice input requires Chrome (or a Chromium-based browser); it isn't available in all browsers

## Future scope

- More Indian languages (Malayalam, Telugu, Kannada)
- Direct document upload from the UI with OCR for scanned PDFs
- Mobile app wrapper
- Role-based access for multi-team knowledge bases
- Analytics on frequently asked / frequently unanswered questions

## Project structure

```
nexus-rag/
├── app.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── data/documents/          <- put your knowledge base files here
├── vectorstore/              <- ChromaDB persistent storage (auto-created)
├── src/
│   ├── config.py
│   ├── document_loader.py
│   ├── chunker.py
│   ├── embeddings.py
│   ├── vector_store.py
│   ├── retriever.py
│   ├── llm.py
│   ├── rag_pipeline.py
│   ├── language.py
│   ├── memory.py
│   ├── citations.py
│   └── indexer.py
├── prompts/rag_prompt.txt
├── static/js/app.js
├── templates/index.html
└── tests/
    ├── test_retrieval.py
    ├── test_rag.py
    └── test_language.py
```

## Testing

```bash
pytest tests/
```

`test_rag.py`'s full end-to-end test is skipped automatically if `LLM_API_KEY` isn't set; retrieval and language tests run regardless.

## Feature checklist

| Requirement | Status |
|---|---|
| Document ingestion (PDF/TXT/DOCX) | Done |
| Chunking with overlap, configurable | Done |
| Multilingual embeddings | Done |
| Persistent vector database | Done |
| Retrieval with relevance threshold | Done |
| LLM integration, provider-agnostic | Done |
| English/Tamil/Hindi support | Done |
| Cross-language retrieval | Done |
| Conversation memory | Done |
| Document selection / filtering | Done |
| Source citations with page numbers | Done |
| Evidence view | Done |
| Hallucination protection | Done |
| Voice input | Done (browser-based) |
| Text-to-speech | Done (browser-based) |
| Professional UI | Done |
| Error handling | Done |
| Tests | Done |
| README + setup docs | Done |
| Local/offline LLM option | Done (Ollama provider) |
