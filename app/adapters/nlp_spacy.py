"""
NLP adapter for topic extraction (slides -> primary topic + subtopics).

Priority:
  1) Weighted phrase scoring (regex over curated CS terms + synonyms)
  2) spaCy noun-phrase frequency (if en_core_web_sm is available)
  3) Heuristic n-gram fallback

Smart merges:
  - variables + (loops|for-loops|while-loops)         -> "variables-and-loops"
  - conditionals + (loops|for-loops|while-loops)      -> "control-flow"
  - functions + recursion                             -> "functions-and-recursion"
  - arrays|strings|dictionaries|sets                  -> "data-structures" (if >1 DS category)
  - sorting|searching|big-o                          -> "algorithms" (if algo family dominates)

Output:
  (primary_slug: str, subtopics: list[str] up to 2)
"""

from __future__ import annotations
from typing import List, Tuple, Iterable, Dict, Optional
import logging
from collections import Counter, defaultdict
import re


# Normalisation helpers

_WORD = re.compile(r"[a-z0-9]+")

def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()

def _words(text: str) -> List[str]:
    return _WORD.findall(text.lower())

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "topic"

def _ngrams(tokens: List[str], n: int) -> Iterable[str]:
    for i in range(len(tokens) - n + 1):
        yield " ".join(tokens[i : i + n])

# Curated phrase dictionary
#   - keys are canonical categories/slugs
#   - values: (weight, [regex patterns])

def _rx(s: str) -> re.Pattern:
    return re.compile(s, re.IGNORECASE)

PHRASES: Dict[str, tuple[int, list[re.Pattern]]] = {
    # Fundamentals
    "variables": (3, [_rx(r"\bvariable(s)?\b"), _rx(r"\bassignment\b"), _rx(r"\bdata\s*types?\b"),
                       _rx(r"\bconstant(s)?\b"), _rx(r"\b(type\s*casting|cast)\b")]),
    "operators": (2, [_rx(r"\b(arithmetic|logical|comparison)\s+operator(s)?\b"),
                      _rx(r"\b\+|-|\*|/|%|==|!=|<=|>=\b")]),
    "input-output": (2, [_rx(r"\binput\b"), _rx(r"\boutput\b"), _rx(r"\bstdin\b"), _rx(r"\bstdout\b")]),
    # Control flow
    "loops": (3, [_rx(r"\bloop(s)?\b"), _rx(r"\biteration\b")]),
    "for-loops": (4, [_rx(r"\bfor\s*loop(s)?\b"), _rx(r"\bfor\s*\("), _rx(r"\bfor\s+each\b")]),
    "while-loops": (4, [_rx(r"\bwhile\s*loop(s)?\b"), _rx(r"\bwhile\s*\(")]),
    "do-while-loops": (4, [_rx(r"\bdo-while\b")]),
    "conditionals": (3, [_rx(r"\bif\s*statements?\b"), _rx(r"\bif-else\b"), _rx(r"\bswitch\s*case\b"),
                          _rx(r"\bbranch(ing)?\b"), _rx(r"\bconditional(s)?\b")]),
    # Functions & program structure
    "functions": (3, [_rx(r"\bfunction(s)?\b"), _rx(r"\bdef\b"), _rx(r"\bparameter(s)?\b"),
                      _rx(r"\bargument(s)?\b"), _rx(r"\breturn\b")]),
    "recursion": (4, [_rx(r"\brecursion\b"), _rx(r"\brecursive\b"), _rx(r"\bbase\s*case\b")]),
    "exceptions": (2, [_rx(r"\bexception(s)?\b"), _rx(r"\btry\s*\/?\s*except\b"), _rx(r"\berror\s*handling\b")]),
    "modules": (1, [_rx(r"\bmodule(s)?\b"), _rx(r"\bpackage(s)?\b"), _rx(r"\bimport\b")]),
    # Data structures
    "arrays": (3, [_rx(r"\barray(s)?\b"), _rx(r"\blist(s)?\b"), _rx(r"\bvector(s)?\b")]),
    "strings": (3, [_rx(r"\bstring(s)?\b"), _rx(r"\btext\b"), _rx(r"\bcharacter(s)?\b")]),
    "dictionaries": (3, [_rx(r"\bdictionary\b"), _rx(r"\bhash\s*map\b"), _rx(r"\bmap(s)?\b"),
                         _rx(r"\bassoc(iative)?\s*array\b")]),
    "sets": (2, [_rx(r"\bset(s)?\b")]),
    "tuples": (2, [_rx(r"\btuple(s)?\b")]),
    "stacks": (2, [_rx(r"\bstack(s)?\b"), _rx(r"\bpush\b"), _rx(r"\bpop\b")]),
    "queues": (2, [_rx(r"\bqueue(s)?\b"), _rx(r"\benqueue\b"), _rx(r"\bdequeue\b")]),
    "trees": (2, [_rx(r"\btree(s)?\b"), _rx(r"\bbinary\s*tree\b"), _rx(r"\bbst\b")]),
    "graphs": (2, [_rx(r"\bgraph(s)?\b"), _rx(r"\bdfs\b"), _rx(r"\bbfs\b")]),
    # Algorithms & complexity
    "sorting": (3, [_rx(r"\bsort(ing)?\b"), _rx(r"\bquick\s*sort\b"), _rx(r"\bmerge\s*sort\b"),
                    _rx(r"\bbubble\s*sort\b"), _rx(r"\binsertion\s*sort\b"), _rx(r"\bselection\s*sort\b")]),
    "searching": (3, [_rx(r"\bsearch(ing)?\b"), _rx(r"\bbinary\s*search\b"), _rx(r"\blinear\s*search\b")]),
    "complexity": (3, [_rx(r"\bbig[\s-]*o\b"), _rx(r"\btime\s*complexity\b"), _rx(r"\bspace\s*complexity\b")]),
    # Persistence / I-O
    "file-io": (1, [_rx(r"\bfile\s*i\/?o\b"), _rx(r"\bread\s*file\b"), _rx(r"\bwrite\s*file\b")]),
    # OOP (in case slides include it)
    "oop": (2, [_rx(r"\bclass(es)?\b"), _rx(r"\bobject(s)?\b"), _rx(r"\binheritance\b"),
                _rx(r"\bpolymorphism\b"), _rx(r"\bencapsulation\b"), _rx(r"\binterface(s)?\b")]),
}

# Families for downstream merging/aggregation
FAMILY = {
    "loops": {"loops", "for-loops", "while-loops", "do-while-loops"},
    "ds": {"arrays", "strings", "dictionaries", "sets", "tuples", "stacks", "queues", "trees", "graphs"},
    "algorithms": {"sorting", "searching", "complexity"},
}


# spaCy one-time init + PhraseMatcher

_SPACY_NLP: Optional["spacy.language.Language"] = None  # type: ignore[name-defined]
_SPACY_MATCHER: Optional["spacy.matcher.PhraseMatcher"] = None  # type: ignore[name-defined]
_SPACY_PHRASES = [
    "for loop", "while loop", "do-while loop",
    "control flow", "iteration",
    "recursion", "base case",
    "data structure", "array", "linked list", "hash map",
]


def _init_spacy_once() -> None:
    """Load spaCy model & PhraseMatcher once per process (no-op if unavailable)."""
    global _SPACY_NLP, _SPACY_MATCHER
    if _SPACY_NLP is not None:
        return
    try:
        import spacy  # type: ignore
        from spacy.matcher import PhraseMatcher  # type: ignore
        # Prefer medium model for better vectors if available, fallback to small
        _SPACY_NLP = None
        for model in ("en_core_web_md", "en_core_web_sm"):
            try:
                _SPACY_NLP = spacy.load(model)
                logging.getLogger("nlp").info("spaCy model loaded: %s", model)
                break
            except Exception:
                continue
        if _SPACY_NLP is None:
            raise RuntimeError("No spaCy model available (en_core_web_md/sm)")
        _SPACY_MATCHER = PhraseMatcher(_SPACY_NLP.vocab, attr="LOWER")
        _SPACY_MATCHER.add(
            "CS_TERMS",
            [_SPACY_NLP.make_doc(p) for p in _SPACY_PHRASES],
        )
    except Exception:
        _SPACY_NLP = None
        _SPACY_MATCHER = None


# Scoring

def _score_phrases(text: str) -> Dict[str, int]:
    """
    Return weighted counts per category key in PHRASES.
    """
    s = _norm(text)
    score: Dict[str, int] = defaultdict(int)
    for key, (w, patterns) in PHRASES.items():
        hits = 0
        for rx in patterns:
            hits += len(rx.findall(s))
        if hits:
            score[key] += w * hits
    return dict(score)

def _merge_categories(score: Dict[str, int]) -> Tuple[str | None, List[str]]:
    """
    Apply merge rules to derive a good primary + subtopics.
    """
    if not score:
        return None, []

    present = {k for k, v in score.items() if v > 0}

    # 1) variables + any loop family -> variables-and-loops
    if "variables" in present and (present & FAMILY["loops"]):
        subs: List[str] = []
        # prefer specific loop types
        for k in ("for-loops", "while-loops", "loops"):
            if k in present:
                subs.append(k)
        if "variables" not in subs:
            subs.append("variables")
        return "variables-and-loops", subs[:2]

    # 2) conditionals + any loop family -> control-flow
    if "conditionals" in present and (present & FAMILY["loops"]):
        subs = []
        for k in ("for-loops", "while-loops", "loops"):
            if k in present:
                subs.append(k)
        if "conditionals" not in subs:
            subs.append("conditionals")
        return "control-flow", subs[:2]

    # 3) functions + recursion -> functions-and-recursion
    if "functions" in present and "recursion" in present:
        subs = ["recursion", "functions"]
        return "functions-and-recursion", subs[:2]

    # 4) multiple DS categories -> data-structures
    if len(present & FAMILY["ds"]) >= 2:
        # pick two most scored DS as subs
        ds_ranked = sorted([(k, score.get(k, 0)) for k in present & FAMILY["ds"]],
                           key=lambda kv: (-kv[1], kv[0]))
        subs = [k for k, _ in ds_ranked[:2]]
        return "data-structures", subs[:2]

    # 5) algorithms family dominance -> algorithms
    if present & FAMILY["algorithms"]:
        alg_ranked = sorted([(k, score.get(k, 0)) for k in present & FAMILY["algorithms"]],
                            key=lambda kv: (-kv[1], kv[0]))
        prime = alg_ranked[0][0]
        others = [k for k, _ in alg_ranked[1:3]]
        # normalise primary to "algorithms" if multiple members present
        primary = "algorithms" if len(alg_ranked) > 1 else prime
        return primary, others[:2]

    # 6) otherwise: top scorer as primary; next two as subs
    ranked = sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))
    primary = ranked[0][0]
    subs = [k for k, _ in ranked[1:3]]
    return primary, subs

# spaCy pass (optional) with PhraseMatcher boosting

def _spacy_topics(slide_texts: List[str]) -> Tuple[str | None, List[str]]:
    _init_spacy_once()
    if _SPACY_NLP is None:
        return None, []
    try:
        doc = _SPACY_NLP("\n".join(slide_texts))  # type: ignore[operator]
        c = Counter()
        # Boost explicit CS phrases
        if _SPACY_MATCHER is not None:
            matches = _SPACY_MATCHER(doc)  # type: ignore[misc]
            for _match_id, start, end in matches:
                phrase = " ".join(_words(doc[start:end].text))
                if phrase:
                    c[phrase] += 6
        # Noun chunks (medium weight)
        for chunk in doc.noun_chunks:
            key = " ".join(_words(chunk.text))
            if len(key) >= 3:
                c[key] += 3
        # Single nouns (light weight)
        for tok in doc:
            if tok.pos_ in {"NOUN", "PROPN"}:
                lemma = tok.lemma_.lower()
                if len(lemma) >= 3:
                    c[lemma] += 1
        if not c:
            return None, []
        ranked = [k for k, _ in c.most_common(12)]
        primary = _slug(ranked[0])
        subs = [_slug(w) for w in ranked[1:3]]
        return primary, subs
    except Exception:
        return None, []

# Heuristic fallback

STOP = {
    "the","and","for","with","that","this","from","your","have","will","into","about",
    "when","where","each","you","are","not","can","but","than","then","else","our",
    "they","them","their","there","here","such","some","most","more","less","few",
    "to","of","in","on","by","as","is","it","be","or","an","a"
}

def _heuristic_topics(slide_texts: List[str]) -> Tuple[str, List[str]]:
    tokens: List[str] = []
    for block in slide_texts:
        tokens.extend([t for t in _words(block) if t not in STOP and len(t) > 2])
    if not tokens:
        return "topic", []

    c = Counter()
    for bg in _ngrams(tokens, 2):
        c[bg] += 2
    for ug in tokens:
        c[ug] += 1

    ranked = [k for k, _ in c.most_common(15)]

    # Normalise helpers for quick checks
    def present(substr: str) -> bool:
        return any(substr in k for k in ranked)

    def any_of(*subs: str) -> bool:
        return any(present(s) for s in subs)

    # 1) variables + any loop term -> variables-and-loops
    if present("variable") and any_of("for loop", "while loop", "loop", "iteration"):
        subs: List[str] = []
        if present("for loop"):
            subs.append("for-loops")
        if present("while loop"):
            subs.append("while-loops")
        if not subs and present("loop"):
            subs.append("loops")
        if "variables" not in subs:
            subs.append("variables")
        return "variables-and-loops", subs[:2]

    # 2) conditionals + any loop term -> control-flow
    if any_of("if ", "if-else", "switch", "conditional", "branch") and any_of("for loop", "while loop", "loop", "iteration"):
        subs: List[str] = []
        if present("for loop"):
            subs.append("for-loops")
        if present("while loop"):
            subs.append("while-loops")
        if not subs and present("loop"):
            subs.append("loops")
        if "conditionals" not in subs:
            subs.append("conditionals")
        return "control-flow", subs[:2]

    # 3) functions + recursion -> functions-and-recursion
    if any_of("function", "def", "procedure", "parameter", "argument") and any_of("recursion", "recursive", "base case"):
        return "functions-and-recursion", ["recursion", "functions"]

    # 4) ≥2 data-structure signals -> data-structures
    ds_hits = {
        "arrays": any_of("array", "list", "vector"),
        "strings": any_of("string", "character", "text"),
        "dictionaries": any_of("dictionary", "hash map", "map", "associative array"),
        "sets": any_of(" set"),
        "tuples": any_of("tuple"),
        "stacks": any_of("stack", "push", "pop"),
        "queues": any_of("queue", "enqueue", "dequeue"),
        "trees": any_of("tree", "binary tree", "bst"),
        "graphs": any_of("graph", "dfs", "bfs"),
    }
    if sum(1 for v in ds_hits.values() if v) >= 2:
        # pick two most obviously present as subs (stable order preference)
        ds_order = [
            "arrays",
            "strings",
            "dictionaries",
            "sets",
            "tuples",
            "stacks",
            "queues",
            "trees",
            "graphs",
        ]
        subs = [k for k in ds_order if ds_hits[k]][:2]
        return "data-structures", subs

    # 5) algorithms family (sorting/searching/complexity)
    alg_hits = {
        "sorting": any_of(
            "sort ",
            "sorting",
            "merge sort",
            "quick sort",
            "bubble sort",
            "insertion sort",
            "selection sort",
        ),
        "searching": any_of("search ", "searching", "binary search", "linear search"),
        "complexity": any_of("big-o", "big o", "time complexity", "space complexity"),
    }
    if any(alg_hits.values()):
        # if multiple algo topics, collapse to 'algorithms'
        present_algs = [k for k, v in alg_hits.items() if v]
        if len(present_algs) > 1:
            subs = present_algs[:2]
            return "algorithms", subs
        else:
            # single dominant algorithm topic becomes primary
            prime = present_algs[0]
            # pick one helpful secondary if available
            others = [k for k in ("sorting", "searching", "complexity") if k != prime and alg_hits[k]]
            return prime, (others[:1])

    # 6) default: top unigram/bigram as primary, next two as subs
    primary = _slug(ranked[0])
    subs = [_slug(x) for x in ranked[1:3]]
    return primary, subs

# Public API


def extract_primary_topic(slide_texts: List[str]) -> Tuple[str, List[str]]:
    """
    Extract (primary_topic_key, subtopics[:2]).
    """
    if not slide_texts:
        return ("topic", [])

    text_all = "\n".join(slide_texts)

    # 1) Weighted phrases
    score = _score_phrases(text_all)
    if score:
        primary, subs = _merge_categories(score)
        if primary:
            return (_slug(primary), [_slug(s) for s in subs])

    # 2) spaCy (if present)
    p2, s2 = _spacy_topics(slide_texts)
    if p2:
        return (p2, s2[:2])

    # 3) Heuristic fallback
    return _heuristic_topics(slide_texts)

__all__ = ["extract_primary_topic"]
