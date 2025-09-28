from __future__ import annotations

import re
from collections import Counter
from typing import List, Tuple

# Attempt to import spaCy if available
try:
    import spacy
    from spacy.util import get_package_path
except Exception:
    spacy = None

# We'll discover installed spaCy models dynamically by checking installed package names
def _discover_spacy_models() -> List[str]:
    if spacy is None:
        return []
    models = []
    # Common model name patterns from spaCy; try to find packages that can be loaded
    candidates = [
        "en_core_web_trf",
        "en_core_web_md",
        "en_core_web_sm",
    ]
    for name in candidates:
        try:
            # Attempt to get package path to verify it's installed
            get_package_path(name)
            models.append(name)
        except Exception:
            continue
    # If none found, attempt to return the spaCy default package name ("en") if possible
    # otherwise return empty list
    return models

# Programming seeds and a small blacklist for nonsense tokens
_PROGRAMMING_SEEDS = {
    "function",
    "variable",
    "loop",
    "list",
    "array",
    "class",
    "python",
    "java",
    "javascript",
    "algorithm",
    "recursion",
    "string",
    "int",
    "float",
    "return",
    "def",
}

_BLACKLIST = {"apple", "apples", "banana", "bananas", "fruit", "fruits", "dog", "cat"}


def _load_best_nlp():
    """Dynamically discover and load the best available spaCy model.

    We do not hardcode models at runtime; instead we probe common model packages and
    load the first that successfully imports. If no spaCy model is available, return None.
    """
    if spacy is None:
        return None
    models = _discover_spacy_models()
    for model in models:
        try:
            return spacy.load(model)
        except Exception:
            continue
    # As a final fallback, try to load spaCy's small English via 'en' or 'en_core_web_sm'
    for fallback in ("en", "en_core_web_sm"):
        try:
            return spacy.load(fallback)
        except Exception:
            continue
    return None


def _normalize(text: str) -> str:
    s = re.sub(r"[^\w\s]", " ", text or "")
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def extract_topics_from_text(text: str, top_n: int = 5) -> Tuple[List[str], str]:
    """
    Extract topics from text using multiple spaCy models and heuristics.
    Returns (topics, domain_label) where domain_label is 'coding' or a short
    domain string (e.g., 'history').
    """
    raw = _normalize(text)
    if not raw:
        return ([], "unknown")
    nlp = _load_best_nlp()
    candidates = Counter()
    domain_votes = Counter()

    # fallback token split candidates
    for token in raw.split():
        if len(token) > 2 and token not in _BLACKLIST:
            candidates[token] += 1

    if nlp:
        doc = nlp(raw)
        # noun chunks and entities
        for chunk in doc.noun_chunks:
            phrase = _normalize(chunk.text)
            if phrase and phrase not in _BLACKLIST:
                candidates[phrase] += 3
                # domain detection
                if any(seed in phrase for seed in _PROGRAMMING_SEEDS):
                    domain_votes["coding"] += 1
        for ent in doc.ents:
            phrase = _normalize(ent.text)
            if phrase and phrase not in _BLACKLIST:
                candidates[phrase] += 2
                if any(seed in phrase for seed in _PROGRAMMING_SEEDS):
                    domain_votes["coding"] += 1

        # token-level checks
        for token in doc:
            t = token.lemma_.lower().strip()
            if t and len(t) > 2 and t not in _BLACKLIST:
                candidates[t] += 1
                if t in _PROGRAMMING_SEEDS:
                    domain_votes["coding"] += 1

    # Promote phrases containing programming seeds
    for phrase in list(candidates.keys()):
        if any(seed in phrase for seed in _PROGRAMMING_SEEDS):
            candidates[phrase] += 10

    # If nothing strong, return first tokens
    if not candidates:
        tokens = [t for t in raw.split() if t not in _BLACKLIST]
        return (tokens[:top_n], "unknown")

    topics = [t for t, _ in candidates.most_common() if t and t not in _BLACKLIST][:top_n]

    # domain label: coding if votes favor it, otherwise try to pick a domain from entities
    domain = "coding" if domain_votes.get("coding", 0) > 0 else "general"

    return (topics, domain)
