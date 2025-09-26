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
from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore
from sklearn.cluster import KMeans  # type: ignore
import numpy as np


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


# Advanced spaCy techniques for general topic extraction

def _extract_keywords_tfidf(slide_texts: List[str]) -> List[str]:
    """Extract keywords using TF-IDF for general topics."""
    if not slide_texts:
        return []
    try:
        vectorizer = TfidfVectorizer(stop_words='english', max_features=50, ngram_range=(1, 2))
        tfidf_matrix = vectorizer.fit_transform(slide_texts)
        feature_names = vectorizer.get_feature_names_out()
        scores = np.sum(tfidf_matrix.toarray(), axis=0)
        top_indices = np.argsort(scores)[-15:][::-1]  # Top 15 for better coverage
        return [feature_names[i] for i in top_indices]
    except Exception as e:
        logging.getLogger("nlp").debug("TF-IDF extraction failed: %s", e)
        return []


def _cluster_keywords(keywords: List[str], n_clusters: int = 3) -> List[List[str]]:
    """Cluster keywords into groups for subtopics using K-means."""
    if len(keywords) < n_clusters:
        return [keywords]
    try:
        vectorizer = TfidfVectorizer(max_features=100)
        X = vectorizer.fit_transform(keywords)
        kmeans = KMeans(n_clusters=min(n_clusters, len(keywords)), random_state=42, n_init=10)
        labels = kmeans.fit_predict(X)
        clusters = defaultdict(list)
        for kw, label in zip(keywords, labels):
            clusters[label].append(kw)
        return list(clusters.values())
    except Exception as e:
        logging.getLogger("nlp").debug("Keyword clustering failed: %s", e)
        # Fallback: split into groups
        return [keywords[i::n_clusters] for i in range(n_clusters)]


def _extract_entities_and_chunks(doc) -> List[str]:
    """Extract named entities and noun chunks from spaCy doc."""
    candidates = []

    # Named entities
    for ent in doc.ents:
        if ent.label_ in ['ORG', 'GPE', 'PERSON', 'EVENT', 'WORK_OF_ART', 'LAW', 'PRODUCT', 'MONEY']:
            candidates.append(ent.text.lower())

    # Noun chunks
    for chunk in doc.noun_chunks:
        chunk_text = chunk.text.lower().strip()
        if len(chunk_text.split()) > 1 and len(chunk_text) > 3:
            candidates.append(chunk_text)

    return candidates


def _extract_important_tokens(doc) -> List[str]:
    """Extract important tokens (nouns, adjectives, verbs) from spaCy doc."""
    important_tokens = []
    for token in doc:
        if (token.pos_ in ['NOUN', 'PROPN', 'ADJ', 'VERB'] and
            not token.is_stop and
            len(token.text) > 2 and
            not token.is_punct and
            not token.is_space):
            important_tokens.append(token.lemma_.lower())
    return important_tokens


def _spacy_advanced_topics(slide_texts: List[str]) -> Tuple[str | None, List[str]]:
    """Advanced topic extraction using multiple spaCy techniques."""
    _init_spacy_once()
    if _SPACY_NLP is None:
        return None, []

    try:
        full_text = "\n".join(slide_texts)
        doc = _SPACY_NLP(full_text)

        # Extract different types of candidates
        entities_chunks = _extract_entities_and_chunks(doc)
        important_tokens = _extract_important_tokens(doc)

        # Combine all candidates
        all_candidates = entities_chunks + important_tokens

        # Score candidates
        counter = Counter(all_candidates)

        # Get TF-IDF keywords for additional weighting
        tfidf_keywords = _extract_keywords_tfidf(slide_texts)
        for kw in tfidf_keywords:
            if kw in counter:
                counter[kw] += 2  # Boost TF-IDF keywords

        # Boost CS-specific phrases if present
        if _SPACY_MATCHER is not None:
            matches = _SPACY_MATCHER(doc)
            for _match_id, start, end in matches:
                phrase = " ".join(_words(doc[start:end].text))
                if phrase:
                    counter[phrase] += 8  # Higher boost for CS terms

        if not counter:
            return None, []

        # Get top keywords
        top_keywords = [kw for kw, _ in counter.most_common(25)]

        # Primary topic: most frequent keyword
        primary = _slug(top_keywords[0])

        # Subtopics: cluster remaining keywords
        remaining_keywords = top_keywords[1:16]  # Use top 15 for clustering
        clusters = _cluster_keywords(remaining_keywords, 3)
        subtopics = []
        for cluster in clusters[:2]:  # Up to 2 subtopics
            if cluster:
                # Use the most frequent keyword from each cluster
                cluster_counter = Counter(cluster)
                representative = cluster_counter.most_common(1)[0][0]
                subtopics.append(_slug(representative))

        return primary, subtopics

    except Exception as e:
        logging.getLogger("nlp").error("Advanced spaCy extraction failed: %s", e)
        return None, []


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
        subs = [k for k, _ in ds_ranked[:3]]
        return "data-structures", subs[:3]

    # 5) algorithms family dominance -> algorithms
    if present & FAMILY["algorithms"]:
        alg_ranked = sorted([(k, score.get(k, 0)) for k in present & FAMILY["algorithms"]],
                            key=lambda kv: (-kv[1], kv[0]))
        prime = alg_ranked[0][0]
        others = [k for k, _ in alg_ranked[1:3]]
        # normalise primary to "algorithms" if multiple members present
        primary = "algorithms" if len(alg_ranked) > 1 else prime
        return primary, others[:3]

    # 6) otherwise: top scorer as primary; next two as subs
    ranked = sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))
    primary = ranked[0][0]
    subs = [k for k, _ in ranked[1:4]]
    return primary, subs

# spaCy pass (optional) with PhraseMatcher boosting

def _spacy_topics(slide_texts: List[str]) -> Tuple[str | None, List[str]]:
    """Enhanced spaCy topic extraction using advanced techniques."""
    # First try advanced extraction
    primary, subs = _spacy_advanced_topics(slide_texts)
    if primary:
        return primary, subs

    # Fallback to basic spaCy extraction
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
        subs = [_slug(w) for w in ranked[1:4]]
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
        return "variables-and-loops", subs[:3]

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
        return "control-flow", subs[:3]

    # 3) functions + recursion -> functions-and-recursion
    if any_of("function", "def", "procedure", "parameter", "argument") and any_of("recursion", "recursive", "base case"):
        return "functions-and-recursion", ["recursion", "functions", "parameters"]

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
        subs = [k for k in ds_order if ds_hits[k]][:3]
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
            subs = present_algs[:3]
            return "algorithms", subs
        else:
            # single dominant algorithm topic becomes primary
            prime = present_algs[0]
            # pick one helpful secondary if available
            others = [k for k in ("sorting", "searching", "complexity") if k != prime and alg_hits[k]]
            return prime, (others[:1])

    # 6) default: top unigram/bigram as primary, next two as subs
    primary = _slug(ranked[0])
    subs = [_slug(x) for x in ranked[1:4]]
    return primary, subs

# Public API


def extract_primary_topic(slide_texts: List[str]) -> Tuple[str, List[str]]:
    """
    Extract (primary_topic_slug, subtopics[:3]) using multiple advanced techniques.

    Combines the best aspects of all methods:
    1) Weighted phrase scoring for CS/programming topics (primary for CS content)
    2) Advanced spaCy techniques (NER, TF-IDF, clustering) for general topics
    3) Heuristic n-gram fallback (supplements with additional subtopics)

    Returns the most appropriate primary topic with up to 3 subtopics.
    """
    if not slide_texts:
        return ("topic", [])

    text_all = "\n".join(slide_texts)
    all_results = []

    # 1) Weighted phrases (best for CS topics)
    score = _score_phrases(text_all)
    weighted_primary = None
    weighted_subs = []
    if score:
        primary, subs = _merge_categories(score)
        if primary:
            weighted_primary = _slug(primary)
            weighted_subs = [_slug(s) for s in subs]
            all_results.append((weighted_primary, weighted_subs, "weighted_phrases", score))

    # 2) Advanced spaCy techniques (best for general topics)
    spacy_primary, spacy_subs = _spacy_topics(slide_texts)
    if spacy_primary:
        all_results.append((spacy_primary, spacy_subs, "spacy_advanced", None))

    # 3) Heuristic fallback (always provides additional subtopics)
    heuristic_primary, heuristic_subs = _heuristic_topics(slide_texts)
    all_results.append((heuristic_primary, heuristic_subs, "heuristic", None))

    if not all_results:
        return ("topic", [])

    # Intelligent combination logic
    def _get_best_primary_and_subs():
        # Determine content type and confidence levels
        cs_confidence = 0
        general_confidence = 0
        cs_primary = None
        cs_subs = []
        general_primary = None
        general_subs = []

        for primary, subs, method, score_data in all_results:
            if method == "weighted_phrases":
                # Calculate CS confidence
                total_score = sum(score_data.values()) if score_data else 0
                cs_indicators = sum(1 for k in score_data.keys() if k in [
                    "variables", "loops", "for-loops", "while-loops", "conditionals",
                    "functions", "arrays", "strings", "dictionaries", "sorting", "searching"
                ])
                if cs_indicators >= 2 and total_score >= 5:
                    cs_confidence = 15  # Very high confidence for clear CS content
                elif cs_indicators >= 1 and total_score >= 3:
                    cs_confidence = 10  # High confidence for some CS content
                cs_primary = primary
                cs_subs = subs

            elif method == "spacy_advanced":
                # Calculate general academic confidence
                if _is_general_academic_topic(primary, subs, slide_texts):
                    general_confidence = 12  # High confidence for general academic topics
                else:
                    general_confidence = 8   # Good confidence for other content
                general_primary = primary
                general_subs = subs

        # Decision logic: Choose primary topic
        if cs_confidence >= general_confidence and cs_primary:
            # Use CS method as primary if it has higher confidence
            final_primary = cs_primary
            base_subs = cs_subs[:]
        elif general_primary:
            # Use general method as primary
            final_primary = general_primary
            base_subs = general_subs[:]
        else:
            # Fallback to heuristic
            final_primary = heuristic_primary
            base_subs = heuristic_subs[:]

        # Combine subtopics from all methods (up to 3 total)
        all_subtopics = set()

        # Add base subtopics first
        for sub in base_subs:
            if len(all_subtopics) < 3:
                all_subtopics.add(sub)

        # Add complementary subtopics from other methods
        for primary, subs, method, _ in all_results:
            if method != ("weighted_phrases" if cs_confidence >= general_confidence else "spacy_advanced"):
                for sub in subs:
                    if sub not in all_subtopics and len(all_subtopics) < 3:
                        all_subtopics.add(sub)

        # If still need more subtopics, add from heuristic
        if len(all_subtopics) < 3:
            for sub in heuristic_subs:
                if sub not in all_subtopics and len(all_subtopics) < 3:
                    all_subtopics.add(sub)

        final_subs = list(all_subtopics)[:3]

        return final_primary, final_subs

    primary, subs = _get_best_primary_and_subs()

    # Heuristic override: if the combined logic picked the broad
    # "variables-and-loops" but the text clearly focuses on tuples,
    # prefer the specific data-structure 'tuples' as the primary topic.
    # This fixes cases where slides repeatedly mention "tuple(s)" but
    # also include incidental "variables" or "loops" wording.
    try:
        text_all = "\n".join(slide_texts).lower()
        # check for explicit tuple mentions in text or subs
        tuple_mentioned = "tuple" in text_all or "tuples" in text_all or any(s in ("tuple", "tuples") for s in subs)
        if primary == "variables-and-loops" and tuple_mentioned:
            primary = "tuples"
            # Rebuild subs: prefer keeping tuple-related and then variables/loops
            new_subs = []
            # include 'tuple' only as primary, avoid duplicating in subs
            # prefer variables and loops as helpful subs if present
            for cand in ("variables", "for-loops", "while-loops", "loops"):
                if cand not in new_subs and cand in text_all:
                    new_subs.append(cand)
            # fill remaining subs from previous subs excluding tuple variants
            for s in subs:
                if s not in ("tuple", "tuples") and s not in new_subs and len(new_subs) < 3:
                    new_subs.append(s)
            subs = new_subs[:3]
    except Exception:
        # Non-fatal; fall back to original primary/subs
        pass

    logging.getLogger("nlp").debug("Combined topic extraction -> %s, %s", primary, subs)
    return primary, subs


def _is_general_academic_topic(primary: str, subs: List[str], slide_texts: List[str]) -> bool:
    """Check if content appears to be general academic (non-CS) topic."""
    text_all = "\n".join(slide_texts).lower()

    # Check for academic subject indicators
    academic_subjects = [
        "biology", "chemistry", "physics", "history", "geography", "literature",
        "mathematics", "economics", "psychology", "sociology", "philosophy",
        "politics", "art", "music", "language", "anthropology"
    ]

    # Check for academic keywords
    academic_keywords = [
        "photosynthesis", "revolution", "artificial intelligence", "machine learning",
        "climate", "evolution", "civilization", "government", "culture", "theory"
    ]

    subject_matches = sum(1 for subject in academic_subjects if subject in text_all)
    keyword_matches = sum(1 for keyword in academic_keywords if keyword in text_all)

    # If we have academic subject/keyword matches and primary topic looks academic
    if (subject_matches > 0 or keyword_matches > 0) and primary not in [
        "variables", "loops", "functions", "conditionals", "operators"
    ]:
        return True

    return False

__all__ = ["extract_primary_topic"]
