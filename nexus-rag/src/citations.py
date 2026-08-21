"""
Formats retrieved chunks into citation and evidence structures for the API.
Never invents a source or page — only reports what retrieval actually returned.
"""
from typing import List, Dict


def build_sources(chunks: List[Dict]) -> List[Dict]:
    """De-duplicated list of {source, page} for the 'Sources' row."""
    seen = set()
    sources = []
    for c in chunks:
        key = (c["source"], c["page"])
        if key in seen:
            continue
        seen.add(key)
        sources.append({"source": c["source"], "page": c["page"]})
    return sources


def build_evidence(chunks: List[Dict]) -> List[Dict]:
    """Full evidence list for the 'View evidence' expandable section."""
    evidence = []
    for c in chunks:
        evidence.append({
            "source": c["source"],
            "page": c["page"],
            "relevance_score": c["score"],
            "relevance_label": _relevance_label(c["score"]),
            "passage": c["text"][:400] + ("..." if len(c["text"]) > 400 else ""),
        })
    return evidence


def _relevance_label(score: float) -> str:
    if score >= 0.6:
        return "High"
    if score >= 0.4:
        return "Medium"
    return "Low"
