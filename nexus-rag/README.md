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
| LLM | Groq `openai/gpt-oss-120b` (swappable to Gemini/OpenAI/xAI/Ollama) | Free tier, sub-second latency, verified to answer correctly in Tamil and Hindi |
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

Then edit `.env` and set two values:

```bash
LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-120b
LLM_API_KEY=gsk_your_key_here
```

Get a free Groq key at https://console.groq.com/keys (no credit card).

**Model choice matters here.** Groq accounts differ in which models they expose — list yours with `client.models.list()`. `openai/gpt-oss-120b` was chosen after testing candidates on a Tamil prompt: it answered correctly in 0.9s, while `qwen/qwen3.6-27b` leaked raw `<think>` reasoning blocks and produced no Tamil at all.

To use a different provider, change `LLM_PROVIDER` to `gemini`, `openai`, `xai` (Grok), or `ollama` and set the matching key and model. `LLM_BASE_URL` overrides the endpoint for any OpenAI-compatible API.

## Knowledge base setup

The knowledge base has two tiers.

**Provided documents** — place your official Round 2 documents (`.pdf`, `.txt`, `.md`, or `.docx`) in:

```
data/documents/
```

These are indexed once on first startup and are answerable from every chat. They are never removed by clearing a chat.

**User uploads are disabled.** Nexora answers only from the eight official documents, so every answer is traceable to institutional policy. The per-chat upload machinery (scoped indexing, isolation, cleanup) is implemented and tested but gated behind `UPLOADS_ENABLED` in `src/config.py` — set it to `1` to restore it.

## Indexing

The app automatically indexes the knowledge base on first startup if it hasn't been indexed yet. To force a full rebuild (e.g. after adding new documents), either:

- Click **Rebuild knowledge base** in the sidebar, or
- Run: `python -c "from src.indexer import ensure_base_index; ensure_base_index(force=True)"`

The first run downloads the multilingual embedding model (~1GB, one-time, requires internet).

## Running

```bash
python app.py
```

Then open http://localhost:5000 — the landing page. The assistant console is at `/app`.

On macOS, port 5000 is taken by AirPlay Receiver; use another port:

```bash
PORT=5001 python app.py
```

If the machine is offline after the embedding model has been downloaded once, add `HF_HUB_OFFLINE=1` to skip slow Hugging Face reachability checks.

## Example questions

- English: *What is the minimum attendance requirement?*
- Tamil: *குறைந்தபட்ச வருகைத் தேவை என்ன?*
- Hindi: *न्यूनतम उपस्थिति की आवश्यकता क्या है?*
- Follow-up: *What happens if I don't meet it?*
- Unsupported: *What is the population of Japan?* → returns "not found in knowledge base" instead of guessing

## How retrieval works

Every document is split into overlapping chunks (default ~250 words, ~60-word overlap) that preserve source filename and page number. Each chunk is embedded with a multilingual model and stored in ChromaDB. When a question comes in — in any supported language — it's embedded with the same model and compared against all stored chunks by cosine similarity. Because the embedding model is multilingual, a Tamil question and its semantically equivalent English sentence land close together in vector space, so the correct English chunk is retrieved even though the question wasn't in English.

## Hallucination protection

Retrieved chunks below `RELEVANCE_THRESHOLD` (default 0.35, adjustable in the sidebar) are discarded before the LLM ever sees them. If nothing clears the bar, the app returns a fixed "not found in knowledge base" message in the user's language without calling the LLM at all — so an ungrounded answer is structurally impossible, not just prompted against.

## Reliability engineering

The brief asks for a *reliable* RAG assistant. Reliability here is structural, not prompted — each mechanism below is enforced in code and covered by a test.

**1. The hallucination guard is a filter, not an instruction.**
Chunks scoring below `RELEVANCE_THRESHOLD` (0.35 cosine) are discarded in `retriever.retrieve()` *before* the prompt is built. If nothing survives, `rag_pipeline` returns a fixed message and never calls the LLM at all. An ungrounded answer is structurally impossible, not merely discouraged. Verified: *"What is the population of Japan?"* tops out at 0.224 and is refused.

**2. The corpus is closed.**
Only the eight official documents are indexed. User uploads are disabled (`UPLOADS_ENABLED=0`), so no unofficial text can ever become a citation. A placeholder handbook that shipped in `data/documents/` was found to be outranking the real policies (0.750 vs 0.734 on attendance) and was moved to `data/_excluded/`.

**3. Follow-up questions inherit context — carefully.**
A pronoun-only follow-up such as *"what happens if I don't meet it?"* embeds to nothing: it scores 0.160 and would be refused. When the bare query fails **and** the question contains a referring token (`it`, `that`, `அது`, `वह`, …), retrieval retries with the previous question prepended, which lifts it to 0.719. The gate matters: prepending unconditionally made *"What is the population of Japan?"* retrieve attendance chunks after an attendance question — an ungrounded answer created by the fix itself. Both behaviours are regression-tested.

**4. Questions about the corpus are answered from the index.**
*"What do you know?"* is a question about the knowledge base, not one the documents can answer — every chunk embeds far away from it (top score 0.128). Rather than a dead end, `rag_pipeline` detects these and lists the indexed documents directly, in English, Tamil or Hindi.

**5. Citations cannot be fabricated.**
`citations.py` builds sources only from chunks that retrieval actually returned; the LLM is explicitly instructed not to emit citations in its answer text. Source names, page numbers and relevance scores come from vector-store metadata, never from the model.

**6. The retrieval is inspectable.**
The semantic map projects every chunk to 2D with PCA (`semantic_map.py`) and draws a constellation from the question to the chunks that answered it. Alongside it, the evidence table shows each retrieved passage with its score. A grader can see *why* an answer was given, not just what it said.

## Limitations

- Speech recognition accuracy for Tamil and Hindi depends on the browser's built-in engine and can vary with accent/microphone quality
- Answer quality depends entirely on the connected LLM provider and the quality/coverage of the source documents
- Cross-language retrieval quality depends on the multilingual embedding model — very short or ambiguous queries retrieve less reliably
- Web Speech API voice input requires Chrome (or a Chromium-based browser); it isn't available in all browsers

## Future scope

- More Indian languages (Malayalam, Telugu, Kannada)
- OCR for scanned PDFs, and re-enabling scoped user uploads for non-policy corpora
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
├── data/documents/          <- the eight official policy documents
├── data/_excluded/          <- non-official files kept out of the index
├── vectorstore/              <- ChromaDB persistent storage (auto-created, gitignored)
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
│   ├── semantic_map.py      <- PCA projection for the retrieval map
│   └── indexer.py
├── prompts/rag_prompt.txt
├── static/js/               <- app.js, vector-sky.js, split-text.js, …
├── templates/landing.html   <- marketing page  (/)
├── templates/index.html     <- assistant console (/app)
└── tests/
    ├── conftest.py
    ├── test_retrieval.py
    ├── test_rag.py
    └── test_language.py
```

## Testing

```bash
pytest tests/
```

30 tests cover retrieval, scope isolation, language detection and resolution, the hallucination guard, follow-up context inheritance, and corpus-listing questions. `test_rag.py`'s full end-to-end test skips automatically if `LLM_API_KEY` isn't set; everything else runs regardless.

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
