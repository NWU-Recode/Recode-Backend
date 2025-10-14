from __future__ import annotations

import re
from collections import Counter
from typing import List, Tuple, Dict

try:
    import spacy
    from spacy.util import get_package_path
except Exception:
    spacy = None

#CS coding topics with multi-word phrases prioritized as they have more meaning 
CS_TOPICS = {
    #file/IO operations
    "file handling", "file operations", "file io", "input output",
    "reading files", "writing files", "file streams", "text files",
    "csv files", "json files", "file modes", "file paths",
    
    #data structures - saw with some cmpg111 contains lists
    "data structures", "linked lists", "binary trees", "hash tables",
    "stacks", "queues", "graphs", "heaps", "nested lists",
    "list comprehension", "dictionary methods", "set operations", "2D arrays",# CS Topics with multi-word phrases prioritized

    
    #basic data types
    "data types", "type conversion", "type casting", "variable assignment",
    "variable scope", "global variables", "local variables", "constants",
    "string concatenation", "string formatting", "string methods",
    "numeric types", "boolean logic", "none type",
    
    #operators
    "arithmetic operators", "comparison operators", "logical operators",
    "assignment operators", "membership operators", "identity operators",
    "operator precedence", "bitwise operators",
    
    #control Flow
    "control flow", "conditional statements", "if statements", "else statements",
    "elif statements", "nested conditionals", "ternary operators",
    
    #loops
    "for loops", "while loops","do-while loops", "nested loops", "loop control",
    "break statement", "continue statement", "range function",
    "loop iteration", "iterating lists", "iterating dictionaries",
    
    #everything related to functions
    "function definition", "function parameters", "function arguments",
    "return statements", "default parameters", "keyword arguments",
    "positional arguments", "variable arguments", "function scope",
    "lambda functions", "anonymous functions", "higher order functions",
    "recursion", "recursive functions", "base case",
    
    #lists & Sequences
    "list operations", "list indexing", "list slicing", "list methods",
    "append method", "extend method", "insert method", "remove method",
    "pop method", "sort method", "reverse method", "list sorting",
    "mutable sequences", "immutable sequences",
    
    #tuples
    "tuple packing", "tuple unpacking", "tuple operations",
    
    #dictionaries
    "key value pairs", "dictionary operations", "dictionary keys",
    "dictionary values", "dictionary items", "dictionary comprehension",
    
    #sets
    "set operations", "set union", "set intersection", "set difference",
    "set methods", "unique elements",
    
    #strings
    "string operations", "string indexing", "string slicing",
    "string manipulation", "string comparison", "substring",
    "split method", "join method", "strip method", "replace method",
    "upper method", "lower method", "format method", "f strings",
    
    #i/o
    "user input", "print function", "input function", "console output",
    "formatted output", "string interpolation",
    
    #error Handling
    "exception handling", "try except", "try except finally",
    "error handling", "raising exceptions", "custom exceptions",
    "exception types", "syntax errors", "runtime errors", "logic errors",
    
    #OOP Basics (incase)
    "object oriented programming", "classes", "objects", "methods",
    "attributes", "constructors", "init method", "self parameter",
    "instance variables", "class variables", "instance methods",
    "inheritance", "polymorphism", "encapsulation", "abstraction",
    
    #modules,imports
    "modules", "importing modules", "import statement", "from import",
    "standard library", "built in functions", "custom modules",
    
    #basic algorithms
    "linear search", "binary search", "bubble sort", "selection sort",
    "insertion sort", "sorting algorithms", "searching algorithms",
    
    #boolean & logic
    "boolean expressions", "truth tables", "logical and", "logical or",
    "logical not", "short circuit evaluation",
    
    #common patterns
    "accumulator pattern", "counter pattern", "flag variables",
    "sentinel values", "swapping variables",
    
    #testing & debugging
    "debugging", "print debugging", "testing", "test cases",
    "edge cases", "boundary conditions",
    
    #single-word topics (lower priority as less specific) 
    "arrays", "lists", "strings", "dictionaries", "sets", "tuples",
    "variables", "operators", "functions", "loops", "conditionals",
    "recursion", "modules", "debugging", "testing", "comments",
}

# These are supporting concepts, not main topics but support them 
SUPPORTING_CONCEPTS = {
    #keywords
    "int", "float", "string", "str", "char", "boolean", "bool", "void",
    "print", "input", "output", "return", "def", "class", "pass",
    "if", "else", "elif", "while", "for", "import", "from", "as",
    "try", "except", "finally", "raise", "with", "lambda", "yield",
    "true", "false", "none", "and", "or", "not", "in", "is",
    "break", "continue", "global", "nonlocal", "assert", "del",
    
    #common method names (not topics themselves)
    "append", "extend", "insert", "remove", "pop", "sort", "reverse",
    "split", "join", "strip", "replace", "upper", "lower", "format",
    "len", "range", "enumerate", "zip", "map", "filter", "sum", "max", "min",
}
#words that may appear but should not be topics!!
_BLACKLIST = {
    "example", "examples", "slide", "slides", "lecture", "lectures",
    "week", "weeks", "chapter", "chapters", "section", "sections",
    "page", "pages", "exercise", "exercises", "assignment", "assignments",
    "tutorial", "tutorials", "lesson", "lessons", "introduction",
    "overview", "summary", "review", "question", "questions",
    "activity", "activities", "practice", "homework",
}

def _is_main_topic(candidate: str) -> bool:
    #check if candidate is a main topic (not supporting concept) will return true if valid topic and false if supporting concept ot blacklist
    c = candidate.lower().strip()
    
    if c in _BLACKLIST or c in SUPPORTING_CONCEPTS:
        return False

    if c in CS_TOPICS and " " in c:
        return True
 
    if c in CS_TOPICS:
        return len(c) >= 4  # "sets", "heap" ok, "int", "for" not
    
    return False

#Extract multi-word CS phrases with partial matching
def _extract_phrases(text: str) -> List[str]:
    text_lower = text.lower()
    found_phrases = []
    
    for phrase in CS_TOPICS:
        if " " in phrase:  #only multi-word phrases
            #exact match gets added
            if phrase in text_lower:
                found_phrases.append(phrase)
            else:
                words = phrase.split()
                if len(words) == 2:
                    #check if both words appear close together (within 5 words)
                    pattern = rf'\b{words[0]}\b.{{0,50}}\b{words[1]}\b'
                    if re.search(pattern, text_lower):
                        found_phrases.append(phrase)
    
    return found_phrases


def _discover_spacy_models() -> List[str]:
    if spacy is None:
        return []
    models = []
    candidates = ["en_core_web_trf", "en_core_web_md", "en_core_web_sm"]
    for name in candidates:
        try:
            get_package_path(name)
            models.append(name)
        except Exception:
            continue
    return models


def _load_best_nlp():
    if spacy is None:
        return None
    models = _discover_spacy_models()
    for model in models:
        try:
            return spacy.load(model)
        except Exception:
            continue
    for fallback in ("en", "en_core_web_sm"):
        try:
            return spacy.load(fallback)
        except Exception:
            continue
    return None

#remove all punctuation,,keep only words and spaces. make multiple sentences intoone
def _normalize(text: str) -> str:
    s = re.sub(r"[^\w\s]", " ", text or "")
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s

#Check
def extract_topics_from_slides(
    slide_texts: List[str],
    top_n: int = 5
) -> Tuple[List[str], str]:
    """
    Extract topics with slide structure awareness.
    
    Args:
        slide_texts: List where each item is a slide's text.
                     Typically formatted as ["Title", "Body content"]
        top_n: Number of topics to return
    
    Returns:
        (topics, domain) where topics are ranked by relevance
    """
    if not slide_texts:
        return ([], "unknown")
    
    nlp = _load_best_nlp()
    candidates = Counter()
    
    #phase 0: Extract from slide titles (first line of each slide)
    for slide_text in slide_texts:
        if not slide_text:
            continue
        
        # Split into lines and treat first line as title
        lines = slide_text.split('\n')
        if lines:
            title = lines[0].strip()
            if title and len(title) > 5:  # Meaningful title
                # Check if title contains a CS topic phrase
                title_phrases = _extract_phrases(title)
                for phrase in title_phrases:
                    candidates[phrase] += 100  # MASSIVE weight for title phrases
                
                # Also check title words
                title_normalized = _normalize(title)
                for word in title_normalized.split():
                    if len(word) > 3 and _is_main_topic(word):
                        candidates[word] += 50  # High weight for title words
    
    #phase 1: HEAVY weighting for multi-word phrases throughout
    all_text = "\n".join(slide_texts)
    phrases = _extract_phrases(all_text)
    for phrase in phrases:
        candidates[phrase] += 40  # High weight for phrase matches
    
    #phase 2: Process each slide with positional weighting
    for idx, slide_text in enumerate(slide_texts):
        # First slide gets highest weight
        if idx == 0:
            position_weight = 8
        elif idx < 3:
            position_weight = 4
        else:
            position_weight = 1
        
        raw = _normalize(slide_text)
        if not raw:
            continue
        
        #extract with spaCy if available
        if nlp:
            doc = nlp(raw)
            
            #Noun chunks
            for chunk in doc.noun_chunks:
                phrase = _normalize(chunk.text)
                if phrase and len(phrase) > 3:
                    if _is_main_topic(phrase):
                        candidates[phrase] += (3 * position_weight)
            
            #Entities
            for ent in doc.ents:
                phrase = _normalize(ent.text)
                if phrase and _is_main_topic(phrase):
                    candidates[phrase] += (2 * position_weight)

            for token in doc:
                t = token.lemma_.lower().strip()
                if t and len(t) > 3:
                    if _is_main_topic(t):
                        candidates[t] += (1 * position_weight)
        else:
            #Fallback: word frequency
            for word in raw.split():
                if len(word) > 3 and _is_main_topic(word):
                    candidates[word] += (1 * position_weight)
    
    #phase 3:Rank and filter with debug output
    print(f"\n[EXTRACTOR DEBUG] Top 15 candidates by score:")
    for topic, score in candidates.most_common(15):
        print(f"  {score:4d} - {topic}")
    
    ranked = candidates.most_common(top_n * 3)
    
    # Separate multi-word from single-word
    multi_word = [(t, c) for t, c in ranked if " " in t]
    single_word = [(t, c) for t, c in ranked if " " not in t]
    
    print(f"\n[EXTRACTOR DEBUG] Multi-word phrases found: {[t for t, _ in multi_word[:10]]}")
    print(f"[EXTRACTOR DEBUG] Single words found: {[t for t, _ in single_word[:10]]}")
    
    final_topics = []
    
    # CRITICAL: If we have multi-word phrases, ONLY use those
    if multi_word:
        for topic, count in multi_word[:top_n]:
            final_topics.append(topic)
            if len(final_topics) >= top_n:
                break
    
    # Only add single-word if we don't have enough multi-word
    if len(final_topics) < top_n:
        remaining = top_n - len(final_topics)
        for topic, count in single_word:
            # Skip if it's a substring of an existing multi-word topic
            if any(topic in mt or mt in topic for mt in final_topics):
                continue
            # Only add high-frequency single words
            if count >= 10:  # Increased threshold
                final_topics.append(topic)
                if len(final_topics) >= top_n:
                    break
    
    print(f"[EXTRACTOR DEBUG] Final topics: {final_topics}\n")
    
    domain = "coding" if final_topics else "unknown"
    
    return (final_topics[:top_n], domain)


def extract_topics_from_text(text: str, top_n: int = 5) -> Tuple[List[str], str]:
    """
    Backward compatible wrapper - treats text as single slide.
    Use extract_topics_from_slides() for better results.
    """
    if not text:
        return ([], "unknown")
    
    # Split into pseudo-slides by paragraphs for some structure
    slides = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not slides:
        slides = [text]
    
    return extract_topics_from_slides(slides, top_n)