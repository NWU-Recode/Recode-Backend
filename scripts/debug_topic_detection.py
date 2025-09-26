# Debug script to run topic detection on provided slide extraction
import sys
import os
import json
import asyncio

# Ensure project root is on sys.path so `app` package imports work
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.adapters import nlp_spacy

extraction = {
    "slides": {
        "1": [
            "Introduction to Tuples",
            "Tuples are ordered collections of items in Python.\nUnlike lists, tuples are immutable, meaning they cannot be changed after creation."
        ],
        "2": [
            "Creating Tuples",
            "We use parentheses () to create tuples.\n\nExample:\nfruits = (\"apple\", \"banana\", \"cherry\")\nprint(fruits)"
        ],
        "3": [
            "Single Item Tuples",
            "A tuple with one item needs a comma.\n\nExample:\nsingle = (\"apple\",)\nprint(type(single))"
        ],
        "4": [
            "Accessing Tuple Items",
            "We use indexes to access tuple elements.\n\nExample:\nmy_tuple = (\"apple\", \"banana\", \"cherry\")\nprint(my_tuple[0])  # apple"
        ],
        "5": [
            "Negative Indexing",
            "Negative indexing lets us access from the end.\n\nExample:\nmy_tuple = (\"apple\", \"banana\", \"cherry\")\nprint(my_tuple[-1])  # cherry"
        ],
        "6": [
            "Immutability of Tuples",
            "Tuples cannot be changed after creation.\n\nExample:\nnumbers = (1, 2, 3)\n# numbers[0] = 10 → Error"
        ],
        "7": [
            "Tuple Operations",
            "We can concatenate and repeat tuples.\n\nExample:\nt1 = (1, 2)\nt2 = (3, 4)\nprint(t1 + t2)\nprint(t1 * 3)"
        ],
        "8": [
            "Tuple Unpacking",
            "We can unpack tuple elements into variables.\n\nExample:\nfruits = (\"apple\", \"banana\", \"cherry\")\n(a, b, c) = fruits\nprint(a, b, c)"
        ],
        "9": [
            "Tuples in Loops",
            "Tuples can be used in loops just like lists.\n\nExample:\ncolors = (\"red\", \"green\", \"blue\")\nfor c in colors:\n    print(c)"
        ],
        "10": [
            "Summary",
            "Tuples are immutable, ordered collections.\nThey are created with parentheses, support indexing, and can be unpacked."
        ]
    }
}

async def main():
    # nlp_spacy exposes extract_primary_topic which expects a list of slide texts (strings)
    slides = []
    for idx in sorted(extraction['slides'].keys(), key=lambda x: int(x)):
        parts = extraction['slides'][idx]
        slides.append('\n'.join(parts))

    print('Running nlp_spacy.extract_primary_topic on concatenated slides...')
    # extract_primary_topic is synchronous in the adapter
    try:
        result = nlp_spacy.extract_primary_topic(slides)
        print('\nAdapter result:')
        print(json.dumps({"primary": result[0], "subtopics": result[1]}, indent=2))
    except Exception as e:
        print('Adapter raised an exception: ', e)

if __name__ == '__main__':
    asyncio.run(main())
