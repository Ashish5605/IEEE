"""
Chunking with configurable size/overlap. Splits on sentence boundaries
where possible instead of raw character slicing, to preserve meaning.
"""
import re
from typing import List, Dict
from src.config import CHUNK_SIZE, CHUNK_OVERLAP

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> List[str]:
    sentences = _SENTENCE_SPLIT.split(text.strip())
    return [s for s in sentences if s.strip()]


def _word_count(text: str) -> int:
    return len(text.split())


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Groups sentences into chunks of ~chunk_size words, with ~overlap words
    repeated between consecutive chunks to preserve context across boundaries.
    """
    sentences = _split_sentences(text)
    if not sentences:
        return []

    chunks = []
    current: List[str] = []
    current_words = 0

    for sentence in sentences:
        sw = _word_count(sentence)
        if current_words + sw > chunk_size and current:
            chunks.append(" ".join(current))
            # build overlap tail from the end of the current chunk
            overlap_sentences = []
            overlap_words = 0
            for s in reversed(current):
                overlap_words += _word_count(s)
                overlap_sentences.insert(0, s)
                if overlap_words >= overlap:
                    break
            current = overlap_sentences
            current_words = overlap_words

        current.append(sentence)
        current_words += sw

    if current:
        chunks.append(" ".join(current))

    return chunks


def chunk_documents(documents: List[Dict]) -> List[Dict]:
    """
    Takes raw loaded documents [{source, page, text}, ...] and returns
    chunk records with preserved metadata:
    {chunk_id, source, page, text}
    """
    chunk_records = []
    per_doc_counter = {}

    for doc in documents:
        source = doc["source"]
        page = doc["page"]
        pieces = chunk_text(doc["text"])

        for piece in pieces:
            key = f"{source}_{page if page is not None else 'na'}"
            per_doc_counter[key] = per_doc_counter.get(key, 0) + 1
            idx = per_doc_counter[key]
            chunk_id = f"{source}_{page if page is not None else 'na'}_{idx:03d}"

            chunk_records.append({
                "chunk_id": chunk_id,
                "source": source,
                "page": page,
                "text": piece,
            })

    return chunk_records
