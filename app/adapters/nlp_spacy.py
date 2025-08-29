"""Minimal NLP adapter for topic extraction.

This is a stub that uses simple heuristics to derive a primary topic and
subtopics from raw slide text. It avoids heavyweight spaCy model loading
for the MVP and returns deterministic results.
"""

from __future__ import annotations

from typing import List, Tuple
import re


def _tokenize(text: str) -> List[str]:
    # Lowercase, remove non-alphanum except spaces, split
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
    return [t for t in cleaned.split() if len(t) > 2]


def extract_primary_topic(slide_texts: List[str]) -> Tuple[str, List[str]]:
    """Extract a primary topic key and up to 2 subtopics from slide texts.

    Returns a tuple: (primary_topic_key, subtopics)
    where primary_topic_key is a slug-friendly key like "recursion".
    """
    if not slide_texts:
        return ("topic", [])

    # Simple frequency-based keywording excluding a small stoplist
    stop = {"the", "and", "for", "with", "that", "this", "from", "your", "have", "will",
            "into", "about", "when", "where", "each", "you", "are", "not", "can", "but"}
    counts: dict[str, int] = {}
    for block in slide_texts:
        for tok in _tokenize(block):
            if tok in stop:
                continue
            counts[tok] = counts.get(tok, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    if not ranked:
        return ("topic", [])
    primary = ranked[0][0]
    subs = [w for w, _ in ranked[1:4]]  # up to 3 extras
    return (primary, subs[:2])

__all__ = ["extract_primary_topic"]

