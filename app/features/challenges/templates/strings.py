# Enhanced fallback template for question generation

def template_reverse_string():
    """
    Robust fallback template for string reversal questions.
    This should only be used when AI generation fails.
    """
    return {
        "language_id": 28,  # Python 3
        "starter_code": "def reverse_string(s: str) -> str:\n    \"\"\"\n    Reverse the input string.\n    \n    Args:\n        s: The string to reverse\n    \n    Returns:\n        The reversed string\n    \"\"\"\n    # TODO: Implement this function\n    pass",
        "reference_solution": "def reverse_string(s: str) -> str:\n    \"\"\"\n    Reverse the input string.\n    \n    Args:\n        s: The string to reverse\n    \n    Returns:\n        The reversed string\n    \"\"\"\n    return s[::-1]",
        "tests": [
            {"input": "hello", "expected": "olleh", "visibility": "public"},
            {"input": "world", "expected": "dlrow", "visibility": "public"},
            {"input": "python", "expected": "nohtyp", "visibility": "private"},
            {"input": "", "expected": "", "visibility": "private"},
            {"input": "a", "expected": "a", "visibility": "private"},
            {"input": "racecar", "expected": "racecar", "visibility": "private"}
        ],
        "max_time_ms": 2000,
        "max_memory_kb": 256000,
        "description": "Write a function that reverses a string",
        "title": "String Reversal"
    }
