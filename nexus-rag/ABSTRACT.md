# Nexora — A Reliable RAG Assistant for Institutional Policy

**Northbridge Institute of Technology · AI Domain, Round 2**

---

## Abstract

Students routinely need answers that are buried across dozens of pages of
institutional policy — attendance thresholds, exam eligibility, scholarship
criteria, conduct rules. A general-purpose chatbot will answer such questions
fluently and, often, wrongly: it has no access to the actual regulations and no
way to signal when it is guessing. In a domain where a wrong answer about exam
eligibility has real consequences for a student, fluency without grounding is a
liability rather than a feature.

**Nexora** is a retrieval-augmented generation system built over Northbridge's
eight official policy documents. Every answer is retrieved from those documents
and returned with the source file, page number, and the exact passage that
supports it. When the documents do not contain an answer, the system says so.

The project's central claim is that **reliability must be structural, not
prompted**. Instructing a language model to "only use the provided context" is a
request it can decline. Nexora instead enforces grounding in the retrieval layer:
passages scoring below a cosine-similarity threshold are discarded *before* the
prompt is assembled, and if nothing survives the filter the language model is
never invoked at all. An ungrounded answer is therefore not merely discouraged —
it is unreachable by construction.

A **semantic map** makes retrieval inspectable. Every indexed chunk is projected
to two dimensions by PCA over its stored embedding and drawn as a point; when a
question is asked, the matched chunks brighten and a constellation is drawn from
the question's own projected position to each one. Alongside it, a table lists
each retrieved passage with its relevance score. A grader can see *why* an answer
was produced, not only what it said.

---

## Architecture

```
Eight policy PDFs
      │
      ▼
Document ingestion ──► sentence-aware chunking ──► sentence embeddings
(pypdf)                (250 words / 60 overlap)   (paraphrase-multilingual-
      │                                             mpnet-base-v2, local)
      ▼
ChromaDB persistent vector store  (cosine, metadata: source · page · scope)
      │
      ├──────────────── question (any of three languages)
      │                        │
      ▼                        ▼
 vector search ──────► relevance threshold (0.35)
                               │
                   ┌───────────┴───────────┐
              below threshold          above threshold
                   │                       │
                   ▼                       ▼
        "not in the knowledge      grounded prompt ──► LLM
         base" — no LLM call       (Groq · gpt-oss-120b)
                   │                       │
                   └───────────┬───────────┘
                               ▼
              citations · evidence table · semantic map
                               │
                               ▼
                  Flask JSON API ──► browser client
```

---

## Tools and technologies

### Backend

| Layer | Choice | Why |
|---|---|---|
| Web framework | **Flask 3.0.3** | Small enough to read end to end; no hidden machinery to explain |
| Embeddings | **sentence-transformers 3.0.1** — `paraphrase-multilingual-mpnet-base-v2` | Strong general-purpose sentence encoder. Runs locally: no per-query cost, no data leaving the machine |
| Vector store | **ChromaDB ≥ 0.5.5** | Persistent, cosine similarity, metadata filtering for document-scoped search |
| LLM | **Groq** — `openai/gpt-oss-120b` | Free tier, ~0.9 s responses. Chosen by testing candidates against the corpus: `qwen/qwen3.6-27b` leaked raw `<think>` reasoning into its answers |
| LLM abstraction | Custom provider layer | `LLM_PROVIDER` swaps between Groq, Gemini, OpenAI, xAI (Grok) and Ollama without touching any other file |
| Document parsing | **pypdf 4.3.1**, **python-docx 1.1.2** | PDF page numbers are preserved so citations can name a page |
| Dimensionality reduction | **scikit-learn** PCA | Deterministic (the map does not jump between reloads) and able to project a new query vector using the corpus-fitted transform — which t-SNE and UMAP cannot do natively |
| Testing | **pytest 8.3.2** | 30 tests |

### Frontend

Deliberately **no build step** — HTML, CSS and vanilla ES modules served directly
by Flask, so the project runs with `python app.py` and nothing else.

| Purpose | Choice |
|---|---|
| Styling | Tailwind (CDN) + CSS custom properties for light/dark theming |
| Markdown rendering | marked 12.0.2 |
| Semantic map | Canvas 2D, written for this project |
| Motion / 3D | three.js 0.180, GSAP 3.13, Lenis 1.1.18 (ES modules from CDN) |

### Configuration

| Parameter | Value |
|---|---|
| Chunk size / overlap | 250 words / 60 words |
| Retrieval top-K | 5 (adjustable live in the UI) |
| Relevance threshold | 0.35 cosine (adjustable live in the UI) |
| Conversation memory | last 4 turns |
| Corpus | 8 documents, 10 chunks |

---

## On agents — an explicit note

**Nexora uses no agent framework and no tool-calling.** There is no LangChain,
no LlamaIndex, no CrewAI, no planner, and no multi-step reasoning loop. The
language model is invoked exactly once per question via a single
`chat.completions.create` call with a system prompt and a user prompt, and it
returns prose.

This is a deliberate design decision, not an omission. The task is *retrieve,
filter, ground, answer*. An agent loop would add non-determinism, latency and
failure modes to a pipeline whose entire purpose is predictability — and it would
weaken the central guarantee, because an agent that can decide its own next step
can decide to answer without retrieving. Every control in this system exists
because the flow through it is fixed and inspectable.

All orchestration is ~120 lines of explicit Python in `src/rag_pipeline.py`.

---

## Reliability mechanisms

1. **Threshold filtering precedes prompting.** Sub-threshold chunks are dropped
   in `retriever.retrieve()`; if none survive, `rag_pipeline` returns a fixed
   message without calling the LLM. *"What is the population of Japan?"* peaks at
   0.224 and is refused.

2. **Closed corpus.** Only the eight official documents are indexed; user uploads
   are disabled. A placeholder handbook shipped in the source tree was found to
   be outranking the real policies (0.750 vs 0.734 on attendance) and was removed
   — without which the demonstration would have been citing a fabricated source.

3. **Context-aware follow-ups, carefully bounded.** *"What happens if I don't
   meet it?"* embeds to nothing (0.160) and would be refused. When the bare query
   fails **and** contains a referring token (`it`, `that`, `those`), retrieval
   retries with the previous question prepended, raising it to 0.719. The gate is
   essential: prepending unconditionally caused an unrelated question to retrieve
   the previous topic's chunks — an ungrounded answer created by the fix itself.

4. **Questions about the corpus are answered from the index.** *"What do you
   know?"* scores 0.128 against every chunk. Rather than a dead end, the system
   detects such questions and lists the indexed documents, in the user's language.

5. **Two refusals, not one.** A question scoring below the scope floor (0.22)
   is not an uncovered institutional question — it is about something else, and
   the user is told exactly that. Between the floor and the threshold, the
   answer is "the documents don't cover this". Off-topic questions measure
   0.09–0.17 against the corpus; in-domain ones start at 0.28. Instructions
   embedded in a question are refused by the same gate, before the model runs.

6. **Citations cannot be fabricated.** Source names, pages and scores come from
   vector-store metadata. The model is instructed not to emit citations at all.

---

## Results

| Query | Language | Grounded | Top score |
|---|---|---|---|
| Minimum attendance requirement | English | ✓ | 0.734 |
| "What happens if I don't meet it?" | English follow-up | ✓ | 0.719 (inherited context) |
| Population of Japan | English | ✗ refused | 0.224 |

- **25 automated tests**, covering retrieval, scope isolation, the hallucination
  guard, follow-up inheritance and corpus questions
- **WCAG AA** contrast verified in both themes (dark 7.46–21.00, light 5.90–19.03)
- ~1,650 lines of Python, ~2,100 lines of JavaScript, no build step

---

## Limitations

- The corpus is small (8 single-page documents, 10 chunks); retrieval quality
  claims would need re-testing at scale
  ambiguous queries retrieve less reliably
- Answer quality is bounded by the connected LLM and by the coverage of the
  source documents
