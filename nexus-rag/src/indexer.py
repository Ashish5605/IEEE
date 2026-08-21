"""
Indexing pipeline: documents -> chunks -> embeddings -> vector store.
Everything here is scoped to a chat session_id — each chat has its own
uploaded documents and its own slice of the vector store, so nothing
leaks between chats and clearing/leaving a chat cleans up after itself.
"""
import os
from src import document_loader, chunker, vector_store
from src.config import DOCS_DIR


def session_docs_dir(session_id: str) -> str:
    """Folder where this session's uploaded documents live."""
    return os.path.join(DOCS_DIR, session_id)


def build_index(session_id: str, force: bool = False) -> dict:
    """
    Builds this session's index if it doesn't exist yet, or always rebuilds if force=True.
    Returns a status dict for the API/UI.
    """
    docs_dir = session_docs_dir(session_id)

    if not force and vector_store.is_session_indexed(session_id):
        return {
            "status": "already_indexed",
            "chunks": vector_store.session_chunk_count(session_id),
            "documents": document_loader.list_available_documents(docs_dir),
        }

    documents = document_loader.load_documents(docs_dir)
    if not documents:
        return {
            "status": "no_documents",
            "chunks": 0,
            "documents": [],
            "message": "No supported documents found. Add .pdf, .txt, or .docx files and rebuild.",
        }

    vector_store.delete_session(session_id)
    chunk_records = chunker.chunk_documents(documents)
    vector_store.add_chunks(chunk_records, session_id=session_id)

    return {
        "status": "indexed",
        "chunks": len(chunk_records),
        "documents": document_loader.list_available_documents(docs_dir),
    }


def index_single_document(session_id: str, filename: str) -> dict:
    """
    Incrementally embeds and adds just one document to this session's existing
    index, without wiping/rebuilding everything else. Used after a drag-and-drop
    upload so the new file becomes searchable immediately.
    """
    docs_dir = session_docs_dir(session_id)
    sections = document_loader.load_single_document(docs_dir, filename)
    if not sections:
        return {"status": "no_content", "chunks": 0,
                "message": f"Couldn't extract any text from {filename}."}

    chunk_records = chunker.chunk_documents(sections)
    vector_store.add_chunks(chunk_records, session_id=session_id)

    return {
        "status": "indexed",
        "chunks": len(chunk_records),
        "documents": document_loader.list_available_documents(docs_dir),
    }


def clear_knowledge_base(session_id: str) -> dict:
    """
    Deletes every document this chat session uploaded and wipes its slice of
    the vector index. Uploads are temporary — scoped to one chat — so this
    runs whenever that chat is cleared, replaced by a new one, or navigated
    away from.
    """
    docs_dir = session_docs_dir(session_id)
    removed = document_loader.clear_documents(docs_dir)
    try:
        if os.path.isdir(docs_dir):
            os.rmdir(docs_dir)
    except OSError:
        pass
    vector_store.delete_session(session_id)
    return {"status": "cleared", "files_removed": removed}
