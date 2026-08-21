"""
Document ingestion pipeline.
Supports PDF, TXT, DOCX. Extracts text + page numbers + source metadata.
New formats can be added by registering a loader in LOADERS below.
"""
import os
from typing import List, Dict


def _load_txt(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    return [{"text": text, "page": None}]


def _load_pdf(path: str) -> List[Dict]:
    from pypdf import PdfReader

    reader = PdfReader(path)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            pages.append({"text": text, "page": i + 1})
    return pages


def _load_docx(path: str) -> List[Dict]:
    import docx

    doc = docx.Document(path)
    text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return [{"text": text, "page": None}]


LOADERS = {
    ".txt": _load_txt,
    ".md": _load_txt,
    ".pdf": _load_pdf,
    ".docx": _load_docx,
}


def load_single_document(docs_dir: str, filename: str) -> List[Dict]:
    """Load just one file from the knowledge base folder (used for incremental indexing)."""
    path = os.path.join(docs_dir, filename)
    ext = os.path.splitext(filename)[1].lower()
    loader = LOADERS.get(ext)
    if not loader or not os.path.isfile(path):
        return []

    try:
        sections = loader(path)
    except Exception as e:
        print(f"[document_loader] WARNING: failed to load {filename}: {e}")
        return []

    results = []
    for section in sections:
        if not section["text"].strip():
            continue
        results.append({"source": filename, "page": section["page"], "text": section["text"]})
    return results


def load_documents(docs_dir: str) -> List[Dict]:
    """
    Walk docs_dir and load every supported file.
    Returns a list of dicts: {source, page, text}
    Silently skips unsupported/corrupt files but logs a warning.
    """
    results = []
    if not os.path.isdir(docs_dir):
        return results

    for filename in sorted(os.listdir(docs_dir)):
        path = os.path.join(docs_dir, filename)
        if not os.path.isfile(path):
            continue
        ext = os.path.splitext(filename)[1].lower()
        loader = LOADERS.get(ext)
        if not loader:
            continue
        try:
            sections = loader(path)
        except Exception as e:
            print(f"[document_loader] WARNING: failed to load {filename}: {e}")
            continue

        for section in sections:
            if not section["text"].strip():
                continue
            results.append({
                "source": filename,
                "page": section["page"],
                "text": section["text"],
            })

    return results


def list_available_documents(docs_dir: str) -> List[str]:
    """Names of files in the knowledge base folder that we can actually index."""
    if not os.path.isdir(docs_dir):
        return []
    return sorted([
        f for f in os.listdir(docs_dir)
        if os.path.splitext(f)[1].lower() in LOADERS
    ])


def is_supported_filename(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in LOADERS


def clear_documents(docs_dir: str) -> int:
    """
    Deletes every file in the knowledge base folder (uploads are meant to be
    temporary — scoped to the current chat, not permanent). Returns the count
    of files removed. Never raises if the folder is empty/missing.
    """
    if not os.path.isdir(docs_dir):
        return 0
    removed = 0
    for filename in os.listdir(docs_dir):
        path = os.path.join(docs_dir, filename)
        if os.path.isfile(path):
            try:
                os.remove(path)
                removed += 1
            except OSError as e:
                print(f"[document_loader] WARNING: couldn't remove {filename}: {e}")
    return removed


def save_uploaded_file(docs_dir: str, filename: str, file_bytes: bytes) -> str:
    """
    Saves an uploaded file into the knowledge base folder.
    Rejects unsupported extensions before touching disk.
    Returns the final saved filename (may be suffixed if a name collision occurs).
    """
    if not is_supported_filename(filename):
        raise ValueError(f"Unsupported file type: {filename}. "
                          f"Supported types: {', '.join(sorted(LOADERS.keys()))}")

    os.makedirs(docs_dir, exist_ok=True)

    # Sanitize filename — keep it simple and safe, no path traversal.
    safe_name = os.path.basename(filename).replace("..", "")
    base, ext = os.path.splitext(safe_name)
    final_name = safe_name
    counter = 1
    while os.path.exists(os.path.join(docs_dir, final_name)):
        final_name = f"{base}_{counter}{ext}"
        counter += 1

    with open(os.path.join(docs_dir, final_name), "wb") as f:
        f.write(file_bytes)

    return final_name
