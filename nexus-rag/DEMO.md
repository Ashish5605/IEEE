# Nexora — Demonstration Script

Roughly 5 minutes. Every query below has been run against the live system.

## Setup (before the room is watching)

```bash
cd nexus-rag
HF_HUB_OFFLINE=1 PORT=5001 python app.py
```

Wait for `[startup] base knowledge base: already_indexed (10 chunks)`, then open
http://localhost:5001. Have the console at `/app` in a second tab.

---

## 1. The premise (30s) — landing page

Eight official Northbridge policy documents. Nothing else is indexed.

> "A student asking about attendance shouldn't have to read eight PDFs — and
> shouldn't be told something the policies don't actually say."

Click **Open the console**.

## 2. A grounded answer (45s)

**Ask:** `What is the minimum attendance requirement?`

Point out, in order:
- The answer: **75% in each registered course**
- The **source chips** — document name and page number
- The **semantic map**: a constellation drawn from the question to the four
  chunks that answered it
- The **evidence table**: each passage with its relevance score (top 0.734)

> "Every claim traces to a document. The scores are the actual cosine
> similarities used to decide what the model was allowed to see."

## 3. The refusal — the important one (45s)

**Ask:** `What is the population of Japan?`

> "Nothing cleared the relevance threshold, so the model was never called. This
> isn't the LLM politely declining — retrieval filtered everything out first, so
> there was no context to hallucinate from."

Point at the map: the candidates render as dashed near-misses, not retrievals.

## 4. Multilingual (60s)

**Ask:** `குறைந்தபட்ச வருகைத் தேவை என்ன?`  (Tamil: what is the minimum attendance?)

> "The documents are in English. The question is in Tamil. A multilingual
> embedding model puts them near each other in vector space, so the correct
> English passage is retrieved — and the answer comes back in Tamil."

**Then ask:** `न्यूनतम उपस्थिति की आवश्यकता क्या है?`  (Hindi)

Optionally hit the speaker icon for text-to-speech, or the mic to ask by voice.

## 5. Conversation memory (45s)

**Ask:** `What is the minimum attendance requirement?`
**Then:** `What happens if I do not meet it?`

> "'It' means nothing on its own — that question embeds to a 0.160 score and
> would be refused. It inherits the previous turn's subject, but only because it
> contains a referring word. Ask an unrelated question next and it won't drag
> the old topic along."

**Prove it:** `What is the population of Japan?` → still refused.

## 6. Knowing its own limits (20s)

**Ask:** `What do you know?`

> "A question about the knowledge base, not one the documents answer. It lists
> the eight indexed policies instead of failing."

## 7. Close (30s)

- Retrieval settings: top-K and threshold are live — raise the threshold and the
  same question gets refused, which shows the guard is real
- `pytest tests/ -q` → **30 passed**

> "The design goal was that an ungrounded answer should be structurally
> impossible rather than discouraged by prompt wording."

---

## If something goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| `LLM_API_KEY is not set` | `.env` missing the key | Add it, restart — `.env` is read at import |
| `model_not_found` | Model not on your Groq account | `client.models.list()`, pick an available one |
| Port 5000 in use (macOS) | AirPlay Receiver | `PORT=5001` |
| First query hangs ~30s | Offline HF reachability checks | `HF_HUB_OFFLINE=1` |
| Answers cite `sample_student_handbook` | Placeholder back in the corpus | Move it to `data/_excluded/`, rebuild |
