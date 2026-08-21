"""
Nexora — Flask application.
Serves the frontend UI and exposes the RAG pipeline as a JSON API.
Run with: python app.py

Uploaded documents are temporary: they live only for the current chat
session. Every fresh page load starts a brand-new chat and wipes the
knowledge base of whichever chat was open before (its Q&A transcript is
kept in History, just without the underlying files/index anymore).
"""
import os
import uuid
import traceback
from flask import Flask, request, jsonify, session, render_template

from src import indexer, document_loader, memory, vector_store, chat_history
from src.rag_pipeline import answer_question
from src.config import TOP_K, RELEVANCE_THRESHOLD

MAX_UPLOAD_MB = 20

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "nexus-rag-dev-secret-change-in-production")


def _get_session_id() -> str:
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
    return session["session_id"]


@app.route("/")
def index():
    # Every visit to the app starts a brand-new chat. Whatever chat was open
    # before is preserved in History (its transcript is stored separately),
    # but its uploaded documents/knowledge base are temporary and get wiped.
    old_session_id = session.get("session_id")
    if old_session_id:
        try:
            indexer.clear_knowledge_base(old_session_id)
        except Exception:
            traceback.print_exc()
    session["session_id"] = str(uuid.uuid4())
    return render_template("index.html")


@app.route("/api/status")
def status():
    """Knowledge base status for the sidebar, scoped to the current chat."""
    session_id = _get_session_id()
    docs_dir = indexer.session_docs_dir(session_id)
    return jsonify({
        "indexed": vector_store.is_session_indexed(session_id),
        "chunk_count": vector_store.session_chunk_count(session_id),
        "documents": document_loader.list_available_documents(docs_dir),
        "top_k": TOP_K,
        "relevance_threshold": RELEVANCE_THRESHOLD,
    })


@app.route("/api/rebuild_index", methods=["POST"])
def rebuild_index():
    session_id = _get_session_id()
    try:
        result = indexer.build_index(session_id, force=True)
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": "Couldn't rebuild the knowledge base. Check the server log."}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    question = data.get("question", "")
    source_filter = data.get("source_filter") or None  # None = all documents
    top_k = int(data.get("top_k") or TOP_K)
    threshold = float(data.get("threshold") or RELEVANCE_THRESHOLD)

    session_id = _get_session_id()

    if not vector_store.is_session_indexed(session_id):
        return jsonify({"error": "The knowledge base hasn't been indexed yet. "
                                  "Upload documents in this chat and click 'Rebuild knowledge base'."}), 400

    try:
        result = answer_question(
            question=question,
            session_id=session_id,
            source_filter=source_filter,
            top_k=top_k,
            threshold=threshold,
        )
    except Exception as e:
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
    indexer.clear_knowledge_base(session_id)
    return jsonify({"status": "cleared"})


@app.route("/api/session_transcript")
def session_transcript():
    """Full persisted chat for the current session — used to restore the UI on page load."""
    session_id = _get_session_id()
    return jsonify({"messages": chat_history.load_session(session_id)})


@app.route("/api/new_session", methods=["POST"])
def new_session():
    """Starts a fresh conversation thread and wipes the outgoing chat's temporary
    knowledge base — uploaded documents are scoped to a chat session, not permanent.
    The outgoing chat's transcript remains available in History."""
    old_session_id = session.get("session_id")
    session["session_id"] = str(uuid.uuid4())
    if old_session_id:
        indexer.clear_knowledge_base(old_session_id)
    return jsonify({"session_id": session["session_id"]})


@app.route("/api/history")
def history_list():
    """Summaries of all saved conversation threads, most recent first."""
    return jsonify({"sessions": chat_history.list_sessions()})


@app.route("/api/history/<session_id>", methods=["POST"])
def switch_to_session(session_id):
    """Makes the given saved session the active one, and returns its transcript.
    Note: that chat's uploaded documents were removed when it was left, so its
    transcript is viewable but won't be re-queryable unless new files are added."""
    session["session_id"] = session_id
    return jsonify({"messages": chat_history.load_session(session_id)})


@app.route("/api/upload", methods=["POST"])
def upload_documents():
    """Drag-and-drop / browse upload. Saves each file and indexes it immediately,
    scoped to the current chat session."""
    session_id = _get_session_id()
    docs_dir = indexer.session_docs_dir(session_id)

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
            index_result = indexer.index_single_document(session_id, saved_name)
            results.append({"filename": saved_name, "status": index_result["status"],
                             "chunks": index_result.get("chunks", 0)})
        except Exception as e:
            traceback.print_exc()
            results.append({"filename": f.filename, "status": "error",
                             "message": "Couldn't process this document."})

    return jsonify({"results": results})


@app.route("/favicon.ico")
def favicon():
    return "", 204


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "0") == "1")
