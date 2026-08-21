# Nexora — Reliable RAG Assistant

A retrieval-augmented assistant over Northbridge Institute of Technology's eight
official policy documents. Ask a question in plain English; get an answer drawn
from the policies with the source document, page number and supporting passage.
If the documents don't cover it — or the question isn't about the college at all
— it says so instead of guessing.

Built for the **AI Domain, Round 2** brief.

**The project lives in [`nexus-rag/`](nexus-rag/).**

---

## Start here

| Document | What it covers |
|---|---|
| **[nexus-rag/SETUP.md](nexus-rag/SETUP.md)** | Step-by-step setup on a new machine |
| [nexus-rag/README.md](nexus-rag/README.md) | Architecture, configuration, reliability design |
| [nexus-rag/ABSTRACT.md](nexus-rag/ABSTRACT.md) | Technical abstract and technology rationale |
| [nexus-rag/DEMO.md](nexus-rag/DEMO.md) | Scripted demonstration walkthrough |

---

## Quick start

```bash
cd nexus-rag
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add a free Groq API key
PORT=5001 python app.py       # macOS: 5000 is taken by AirPlay
```

Open <http://localhost:5001>. Full instructions, including Windows and
troubleshooting, are in [SETUP.md](nexus-rag/SETUP.md).

---

## What makes it reliable

Grounding is enforced in the retrieval layer, not requested in the prompt.
Passages below a cosine-similarity threshold are discarded *before* the prompt is
built, and if nothing survives, the language model is never called. An ungrounded
answer isn't discouraged — it's unreachable.

There are two distinct refusals. A question the documents simply don't cover gets
"not in the knowledge base". A question that isn't about the institution at all —
including attempts to override the instructions — is told plainly that it's out
of scope, before any model runs.

| Query | Score | Outcome |
|---|---|---|
| Minimum attendance requirement | 0.734 | Answered, with citations |
| Who is the head of department? | 0.278 | Not covered by the documents |
| How do I cook pasta? | 0.105 | Out of scope |

Retrieval is inspectable: a semantic map projects every indexed chunk to two
dimensions and draws a constellation from the question to the chunks that
answered it, each hoverable for its source and score.

---

## Stack

Flask · ChromaDB · sentence-transformers (local embeddings) · Groq
`openai/gpt-oss-120b` (provider-swappable) · scikit-learn PCA · vanilla ES
modules with no build step · pytest (25 tests).

No agent framework and no tool-calling — the model is invoked once per question.
The reasoning behind that is in [ABSTRACT.md](nexus-rag/ABSTRACT.md).
