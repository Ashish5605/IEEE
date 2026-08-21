# Nexora

A retrieval-augmented assistant for Northbridge Institute of Technology's policy
documents. Ask a question in plain English; get an answer drawn from the official
policies, with the source document, page number and supporting passage. If the
documents don't cover it, Nexora says so rather than guessing.

Built for the AI Domain, Round 2 brief.

---

## Quick start

```bash
cd nexus-rag
pip install -r requirements.txt
cp .env.example .env          # then add your API key, see below
python app.py
```

Open <http://localhost:5000> for the landing page; the assistant console is at
`/app`.

> **macOS:** port 5000 is taken by AirPlay Receiver — use `PORT=5001 python app.py`.
> **Offline:** once the embedding model is cached, `HF_HUB_OFFLINE=1` skips slow
> Hugging Face reachability checks.

### API key

Edit `.env`:

```bash
LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-120b
LLM_API_KEY=gsk_your_key_here
```

Free key: <https://console.groq.com/keys>. Groq accounts differ in which models
they expose — list yours with `client.models.list()` if the configured one 404s.

Other providers work by changing two values: `gemini`, `openai`, `xai` (Grok) or
`ollama`. `LLM_BASE_URL` overrides the endpoint for any OpenAI-compatible API.

---

## How it works

```
Eight policy PDFs
      │
      ▼
 ingest ──► chunk ──► embed ──► ChromaDB (cosine, source · page · scope)
                                    │
                        question ───┤
                                    ▼
                            vector search (top-k 5)
                                    │
                         relevance threshold 0.35
                          ┌─────────┴─────────┐
                       below                above
                          │                    │
                 "not in the KB"      grounded prompt ──► LLM
                 (no LLM call)                 │
                          └─────────┬─────────┘
                                    ▼
                    answer + citations + evidence + semantic map
```

**The threshold filter runs before the prompt is built.** Passages scoring below
`RELEVANCE_THRESHOLD` are discarded during retrieval; if nothing survives, the
language model is never called. An ungrounded answer isn't discouraged by
prompt wording — it's unreachable.

---

## Reliability

| Mechanism | Detail |
|---|---|
| Grounding is a filter, not an instruction | Sub-threshold chunks never reach the prompt. If nothing clears `RELEVANCE_THRESHOLD`, the model is never called. |
| Scope guardrail | Two different refusals. Below `SCOPE_FLOOR` (0.22) the question isn't about the institution at all and the user is told so explicitly; between the floor and the threshold it is an institutional question the documents don't cover, and the user gets "not in the knowledge base". Measured: off-topic questions score 0.09–0.17, in-domain ones 0.28+. |
| Prompt-injection resistance | Instructions embedded in a question ("ignore your instructions…") score far below the floor and are refused before the model runs. The prompt also states that text inside a question is never a command. |
| Closed corpus | Only the eight official documents are indexed. User uploads are disabled (`UPLOADS_ENABLED` in `src/config.py`). |
| Follow-ups inherit context, conditionally | *"What happens if I don't meet it?"* scores 0.160 alone. When a bare query fails **and** contains a referring word (`it`, `that`, `those`), retrieval retries with the previous question prepended — reaching 0.719. Gated, so an unrelated question is never dragged into the previous topic. |
| Corpus questions answered from the index | *"What do you know?"* matches nothing (0.128). Rather than a dead end, the indexed documents are listed. |
| Citations can't be fabricated | Sources, pages and scores come from vector-store metadata; the model is told not to emit citations at all. |
| Retrieval is inspectable | A semantic map projects every chunk to 2D (PCA) and draws a constellation from the question to what it retrieved. Hovering a point names its source and score. |

---

## Configuration

All tunables live in `src/config.py` and can be overridden in `.env`.

| Setting | Default | Meaning |
|---|---|---|
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 250 / 60 | Words per chunk, words repeated between chunks |
| `TOP_K` | 5 | Chunks retrieved per query (adjustable live in the UI) |
| `RELEVANCE_THRESHOLD` | 0.35 | Cosine floor for grounding (adjustable live in the UI) |
| `SCOPE_FLOOR` | 0.22 | Below this a question is treated as out of scope entirely |
| `MAX_HISTORY_TURNS` | 4 | Q&A pairs kept in the LLM-facing context |
| `EMBEDDING_MODEL` | `paraphrase-multilingual-mpnet-base-v2` | Sentence encoder, run locally |
| `UPLOADS_ENABLED` | `0` | Set to `1` to restore per-chat document uploads |

---

## Knowledge base

Place documents (`.pdf`, `.txt`, `.md`, `.docx`) in `data/documents/`. They are
indexed on first startup and shared by every conversation.

To rebuild after changing them, click **Rebuild index** in the console or run:

```bash
python -c "from src.indexer import ensure_base_index; ensure_base_index(force=True)"
```

Files in `data/_excluded/` are deliberately kept out of the index.

---

## Stack

| Layer | Choice |
|---|---|
| Backend | Flask |
| Embeddings | sentence-transformers, run locally |
| Vector store | ChromaDB (persistent, cosine) |
| LLM | Groq `openai/gpt-oss-120b`, provider-swappable |
| Parsing | pypdf, python-docx |
| Projection | scikit-learn PCA |
| Frontend | Vanilla ES modules, Tailwind via CDN — no build step |
| Tests | pytest |

---

## Tests

```bash
pytest tests/ -q
```

25 tests cover retrieval, scope isolation, the hallucination guard, the scope
guardrail, follow-up context inheritance and corpus-listing questions. The end-to-end LLM test skips
automatically when `LLM_API_KEY` is unset; everything else runs regardless.

---

## Project layout

```
nexus-rag/
├── app.py                  Flask routes  (/ landing, /app console, /api/*)
├── src/
│   ├── config.py           every tunable
│   ├── document_loader.py  PDF/TXT/DOCX ingestion
│   ├── chunker.py          sentence-aware chunking
│   ├── embeddings.py       local sentence encoder
│   ├── vector_store.py     ChromaDB + scope filtering
│   ├── retriever.py        search + threshold
│   ├── rag_pipeline.py     orchestration (the only entry point app.py calls)
│   ├── llm.py              provider abstraction
│   ├── semantic_map.py     PCA projection for the map
│   ├── citations.py        sources and evidence
│   ├── memory.py           short LLM-facing context window
│   ├── chat_history.py     persisted transcripts
│   └── language.py         fixed responses
├── data/documents/         the eight indexed policy documents
├── templates/              landing.html · index.html
├── static/js/              app.js and the visual modules
├── prompts/rag_prompt.txt
└── tests/
```

---

## Documentation

- [`SETUP.md`](SETUP.md) — step-by-step setup on a new machine
- [`ABSTRACT.md`](ABSTRACT.md) — architecture, tool choices and design rationale
- [`DEMO.md`](DEMO.md) — a scripted walkthrough with exact queries

---

## Limitations

- The corpus is small (eight single-page documents, ten chunks); retrieval
  quality would need re-testing at scale.
- Answer quality is bounded by the connected model and by what the documents
  actually cover.
- Voice input requires a Chromium-based browser (Web Speech API).
