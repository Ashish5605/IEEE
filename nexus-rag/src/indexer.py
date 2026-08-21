"""
Indexing pipeline: documents -> chunks -> embeddings -> vector store.

Two kinds of knowledge live in the index, separated by "scope":

  * BASE_SCOPE  - the provided knowledge base in data/documents. Ships with the
                  project, indexed once on startup, shared by every chat.
  * session_id  - documents a user uploaded inside one chat, kept in
                  data/uploads/<session_id>. Temporary: wiped when that chat is
                  cleared, replaced, or navigated away from.

A chat searches both of its scopes at once, so the provided documents are always
answerable while one chat's uploads never leak into another's.
"""
import os
import shutil
from typing import List

from src import document_loader, chunker, vector_store
from src.config import BASE_DOCS_DIR, UPLOADS_DIR, BASE_SCOPE


def scopes_for(session_id: str) -> List[str]:
    """Scopes one chat is allowed to search: the shared base plus its own uploads."""
    return [BASE_SCOPE, session_id]


def session_uploads_dir(session_id: str) -> str:
    """Folder holding the documents uploaded inside this chat."""
    return os.path.join(UPLOADS_DIR, session_id)


# --- Base knowledge base (permanent, shared) ---------------------------------

def ensure_base_index(force: bool = False) -> dict:
    """
    Indexes data/documents under BASE_SCOPE. Runs on startup: if the base scope
    already holds chunks it's a no-op, so restarting the server doesn't re-embed
    every PDF. force=True rebuilds it from scratch.
    """
    if not force and vector_store.is_indexed([BASE_SCOPE]):
        return {
            "status": "already_indexed",
            "chunks": vector_store.count_for_scopes([BASE_SCOPE]),
            "documents": document_loader.list_available_documents(BASE_DOCS_DIR),
        }

    documents = document_loader.load_documents(BASE_DOCS_DIR)
    if not documents:
        return {
            "status": "no_documents",
            "chunks": 0,
            "documents": [],
            "message": f"No supported documents found in {BASE_DOCS_DIR}. "
                       f"Add .pdf, .txt, .md or .docx files and rebuild.",
        }

    vector_store.delete_scope(BASE_SCOPE)
    chunk_records = chunker.chunk_documents(documents)
    vector_store.add_chunks(chunk_records, scope=BASE_SCOPE)

    return {
        "status": "indexed",
        "chunks": len(chunk_records),
        "documents": document_loader.list_available_documents(BASE_DOCS_DIR),
    }


# --- Per-chat uploads (temporary) --------------------------------------------

def index_uploaded_document(session_id: str, filename: str) -> dict:
    """
    Embeds one freshly uploaded file into this chat's scope, without rebuilding
    anything else, so a drag-and-drop upload becomes searchable immediately.
    """
    docs_dir = session_uploads_dir(session_id)
    sections = document_loader.load_single_document(docs_dir, filename)
    if not sections:
        return {"status": "no_content", "chunks": 0,
                "message": f"Couldn't extract any text from {filename}."}

    chunk_records = chunker.chunk_documents(sections)
    vector_store.add_chunks(chunk_records, scope=session_id)

    return {
        "status": "indexed",
        "chunks": len(chunk_records),
        "documents": document_loader.list_available_documents(docs_dir),
    }


def rebuild_session_index(session_id: str) -> dict:
    """Re-embeds every file this chat uploaded. The base scope is untouched."""
    docs_dir = session_uploads_dir(session_id)
    documents = document_loader.load_documents(docs_dir)

    vector_store.delete_scope(session_id)
    chunk_records = chunker.chunk_documents(documents) if documents else []
    if chunk_records:
        vector_store.add_chunks(chunk_records, scope=session_id)

    return {
        "status": "indexed",
        "chunks": len(chunk_records),
        "documents": document_loader.list_available_documents(docs_dir),
    }


def clear_session_uploads(session_id: str) -> dict:
    """
    Deletes the files this chat uploaded and drops its slice of the index.
    Guards against ever passing BASE_SCOPE through here — the provided knowledge
    base must survive a chat being cleared.
    """
    if not session_id or session_id == BASE_SCOPE:
        return {"status": "skipped", "files_removed": 0}

    docs_dir = session_uploads_dir(session_id)
    removed = document_loader.clear_documents(docs_dir)
    shutil.rmtree(docs_dir, ignore_errors=True)
    vector_store.delete_scope(session_id)
    return {"status": "cleared", "files_removed": removed}
