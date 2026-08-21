"""
Nexora — Flask application.
Serves the frontend UI and exposes the RAG pipeline as a JSON API.
Run with: python app.py

The knowledge base has two tiers. The documents in data/documents are provided
with the project, indexed once on first startup, and answerable from every chat.
Documents a user uploads are temporary: they belong to the current chat only and
are wiped when that chat is cleared or replaced (the Q&A transcript is kept in
History, just without the underlying files/index).
"""
import os
import uuid
import traceback
from flask import Flask, request, jsonify, session, render_template

from src import indexer, document_loader, memory, vector_store, chat_history, semantic_map
from src.rag_pipeline import answer_question
from src.config import (TOP_K, RELEVANCE_THRESHOLD, SUPPORTED_LANGUAGES,
                        UPLOADS_ENABLED)

MAX_UPLOAD_MB = 20

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "nexus-rag-dev-secret-change-in-production")
# Jinja caches compiled templates when debug is off, so edits to index.html would
# not appear until a restart. This app is run directly for demos, so pick up
# template edits on reload instead.
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True

_base_index_ready = False


def _ensure_base_index():
    """
    Indexes the provided knowledge base on first use. Memoized, and done lazily
    rather than at import time so this works the same under `python app.py`,
    `flask run`, or a WSGI server — and so importing the app stays cheap.
    """
    global _base_index_ready
    if _base_index_ready:
        return
    try:
        result = indexer.ensure_base_index()
        print(f"[startup] base knowledge base: {result['status']} "
              f"({result.get('chunks', 0)} chunks)")
    except Exception:
        traceback.print_exc()
    _base_index_ready = True


def _get_session_id() -> str:
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return session["session_id"]


@app.route("/")
def landing():
    """Marketing/overview page. The console lives at /app."""
    return render_template("landing.html")


@app.route("/app")
def index():
    # Every visit starts a brand-new chat. Whatever chat was open before is
    # preserved in History (its transcript is stored separately), but its
    # uploaded documents are temporary and get wiped. The provided knowledge
    # base is never affected.
    _ensure_base_index()
    old_session_id = session.get("session_id")
    if old_session_id:
        try:
            indexer.clear_session_uploads(old_session_id)
        except Exception:
            traceback.print_exc()
    session["session_id"] = str(uuid.uuid4())
    return render_template("index.html")


@app.route("/api/status")
def status():
    """Knowledge base status for the sidebar: provided documents + this chat's uploads."""
    _ensure_base_index()
    session_id = _get_session_id()
    scopes = indexer.scopes_for(session_id)
    return jsonify({
        "indexed": vector_store.is_indexed(scopes),
        "chunk_count": vector_store.count_for_scopes(scopes),
        "documents": vector_store.sources_in_scopes(scopes),
        "uploaded_documents": document_loader.list_available_documents(
            indexer.session_uploads_dir(session_id)) if UPLOADS_ENABLED else [],
        "uploads_enabled": UPLOADS_ENABLED,
        "top_k": TOP_K,
        "relevance_threshold": RELEVANCE_THRESHOLD,
        "languages": SUPPORTED_LANGUAGES,
    })


@app.route("/api/semantic_map")
def semantic_map_points():
    """
    2D projection of every chunk this chat can search, for the Information
    panel's map. Derived from embeddings already in the index — no LLM call.
    """
    _ensure_base_index()
    session_id = _get_session_id()
    try:
        points = semantic_map.corpus_points(indexer.scopes_for(session_id))
        return jsonify({"points": points})
    except Exception:
        traceback.print_exc()
        return jsonify({"points": []})


@app.route("/api/rebuild_index", methods=["POST"])
def rebuild_index():
    """Re-embeds the provided knowledge base and this chat's uploads from scratch."""
    session_id = _get_session_id()
    try:
        base_result = indexer.ensure_base_index(force=True)
        session_result = indexer.rebuild_session_index(session_id)
        semantic_map.invalidate()
        scopes = indexer.scopes_for(session_id)
        return jsonify({
            "status": base_result["status"],
            "message": base_result.get("message"),
            "chunks": vector_store.count_for_scopes(scopes),
            "documents": vector_store.sources_in_scopes(scopes),
            "uploaded_chunks": session_result.get("chunks", 0),
        })
    except Exception:
        traceback.print_exc()
        return jsonify({"status": "error",
                        "message": "Couldn't rebuild the knowledge base. Check the server log."}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    _ensure_base_index()
    data = request.get_json(silent=True) or {}
    question = data.get("question", "")
    requested_language = data.get("language") or "auto"
    source_filter = data.get("source_filter") or None  # None = all documents
    top_k = int(data.get("top_k") or TOP_K)
    threshold = float(data.get("threshold") or RELEVANCE_THRESHOLD)

    session_id = _get_session_id()
    scopes = indexer.scopes_for(session_id)

    if not vector_store.is_indexed(scopes):
        return jsonify({"error": "The knowledge base hasn't been indexed yet. "
                                 "Click 'Rebuild knowledge base' or upload a document."}), 400

    try:
        result = answer_question(
            question=question,
            session_id=session_id,
            requested_language=requested_language,
            source_filter=source_filter,
            top_k=top_k,
            threshold=threshold,
        )
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "The AI service is currently unavailable. Please try again."}), 500

    if "error" in result:
        return jsonify(result), 400

    # Persist the full transcript so it survives tab switches / page reloads,
    # separately from the short LLM-facing memory window.
    chat_history.append_message(session_id, "user", question)
    chat_history.append_message(session_id, "assistant", result["answer"], meta={
        "sources": result.get("sources", []),
        "evidence": result.get("evidence", []),
        "language": result.get("language"),
    })

    return jsonify(result)


@app.route("/api/clear_chat", methods=["POST"])
def clear_chat():
    session_id = _get_session_id()
    memory.clear_history(session_id)
    chat_history.clear_session(session_id)
    indexer.clear_session_uploads(session_id)
    semantic_map.invalidate()
    return jsonify({"status": "cleared"})


@app.route("/api/session_transcript")
def session_transcript():
    """Full persisted chat for the current session — used to restore the UI on page load."""
    session_id = _get_session_id()
    return jsonify({"messages": chat_history.load_session(session_id)})


@app.route("/api/new_session", methods=["POST"])
def new_session():
    """Starts a fresh conversation thread and wipes the outgoing chat's uploaded
    documents — uploads are scoped to a chat, not permanent. The outgoing chat's
    transcript remains available in History, and the provided knowledge base stays."""
    old_session_id = session.get("session_id")
    session["session_id"] = str(uuid.uuid4())
    if old_session_id:
        indexer.clear_session_uploads(old_session_id)
    return jsonify({"session_id": session["session_id"]})


@app.route("/api/history")
def history_list():
    """Summaries of all saved conversation threads, most recent first."""
    return jsonify({"sessions": chat_history.list_sessions()})


@app.route("/api/history/<session_id>", methods=["POST"])
def switch_to_session(session_id):
    """Makes the given saved session the active one, and returns its transcript.
    Note: that chat's uploaded documents were removed when it was left, so its
    transcript is viewable and the provided knowledge base is still queryable,
    but its old uploads are gone unless re-added."""
    session["session_id"] = session_id
    return jsonify({"messages": chat_history.load_session(session_id)})


@app.route("/api/upload", methods=["POST"])
def upload_documents():
    """Drag-and-drop / browse upload. Saves each file and indexes it immediately,
    scoped to the current chat session. Disabled while Nexora is scoped to the
    fixed college policy corpus (see UPLOADS_ENABLED in src/config.py)."""
    if not UPLOADS_ENABLED:
        return jsonify({"error": "Nexora answers from a fixed set of official "
                                  "college policy documents. Uploads are disabled."}), 403
    _ensure_base_index()
    session_id = _get_session_id()
    docs_dir = indexer.session_uploads_dir(session_id)

    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files received."}), 400

    results = []
    for f in files:
        if not f.filename:
            continue
        if not document_loader.is_supported_filename(f.filename):
            results.append({"filename": f.filename, "status": "rejected",
                            "message": "Unsupported file type."})
            continue

        file_bytes = f.read()
        if len(file_bytes) > MAX_UPLOAD_MB * 1024 * 1024:
            results.append({"filename": f.filename, "status": "rejected",
                            "message": f"File exceeds {MAX_UPLOAD_MB}MB limit."})
            continue

        try:
            saved_name = document_loader.save_uploaded_file(docs_dir, f.filename, file_bytes)
            index_result = indexer.index_uploaded_document(session_id, saved_name)
            semantic_map.invalidate()
            results.append({"filename": saved_name, "status": index_result["status"],
                            "chunks": index_result.get("chunks", 0)})
        except Exception:
            traceback.print_exc()
            results.append({"filename": f.filename, "status": "error",
                            "message": "Couldn't process this document."})

    return jsonify({"results": results})


@app.route("/favicon.ico")
def favicon():
    return "", 204


if __name__ == "__main__":
    _ensure_base_index()
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "0") == "1")
