# Setting up Nexora on another machine

Tested on macOS with Python 3.13. Windows and Linux notes are inline.

Budget **10–15 minutes**, most of it downloading. Two things are large:
PyTorch (a dependency of the embedding library) and the embedding model itself
(~1 GB, downloaded once on first run).

---

## 1. Requirements

- **Python 3.10 or newer** — check with `python3 --version`
- **git**
- An internet connection for the first run
- A free **Groq API key** — <https://console.groq.com/keys> (no credit card)

---

## 2. Get the code

```bash
git clone https://github.com/Ashish5605/IEEE.git
cd IEEE
git checkout feat/reliable-rag-console
cd nexus-rag
```

The eight policy documents are included. The search index is **not** — it is
built automatically the first time the app starts.

---

## 3. Create a virtual environment

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell)**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

You should see `(.venv)` at the start of your prompt. Everything below assumes
it is active.

---

## 4. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This pulls in PyTorch, so expect a few minutes and roughly 2 GB.

---

## 5. Add the API key

```bash
cp .env.example .env      # Windows: copy .env.example .env
```

Open `.env` and set these three lines:

```bash
LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-120b
LLM_API_KEY=gsk_paste_your_key_here
```

No quotes, no spaces around `=`. `.env` is gitignored, so the key stays local.

> **If the model 404s**, that Groq account exposes a different set. List them:
> ```bash
> python -c "from src.config import LLM_API_KEY; from groq import Groq; print([m.id for m in Groq(api_key=LLM_API_KEY).models.list().data])"
> ```
> Pick a chat model from the output and put it in `LLM_MODEL`.

---

## 6. Run it

```bash
python app.py
```

**On macOS use a different port** — port 5000 is taken by AirPlay Receiver:

```bash
PORT=5001 python app.py
```

The first start downloads the embedding model and indexes the eight documents.
Wait for:

```
[startup] base knowledge base: indexed (10 chunks)
 * Running on http://127.0.0.1:5000
```

Then open <http://localhost:5000> — or `:5001` if you changed the port. The
landing page is at `/`, the assistant at `/app`.

Later starts skip both steps and come up in a few seconds.

---

## 7. Check it works

Ask **"What is the minimum attendance requirement?"** — you should get an answer
citing `NB-AR-01` and `NB-AL-03` with page numbers, and the semantic map on the
right should draw lines to the chunks it used.

Then ask **"How do I cook pasta?"** — it should refuse and say it only answers
questions about the college's policy documents. That refusal is the point of
the project, so it is worth demonstrating.

Run the test suite too:

```bash
pytest tests/ -q          # expect: 25 passed
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `LLM_API_KEY is not set` | `.env` missing or unsaved | Check `.env` is in `nexus-rag/`, then restart — it is read once at startup |
| `model_not_found` / 404 | Model not on that Groq account | List available models (step 5) and update `LLM_MODEL` |
| Port 5000 in use (macOS) | AirPlay Receiver | `PORT=5001 python app.py` |
| First query hangs ~30 s | Offline reachability checks | Prefix with `HF_HUB_OFFLINE=1` once the model is cached |
| `ModuleNotFoundError` | Virtual environment not active | Re-run the activate command from step 3 |
| Answers cite `sample_student_handbook` | A placeholder crept into the corpus | It belongs in `data/_excluded/`; move it back and rebuild the index |
| Index looks empty | Vector store not built | `python -c "from src.indexer import ensure_base_index; ensure_base_index(force=True)"` |

---

## Presenting

`DEMO.md` is a scripted walkthrough with the exact queries to run, in order, and
what to point at for each. `ABSTRACT.md` covers the architecture and the
reasoning behind each technology choice.
