def template_reverse_string():
    return {
        "title": "Reverse String",
        "question_text": "Write a function that takes a string as input and returns the string reversed.",
        "difficulty_level": "Bronze",
        "language_id": 28,  # Python
        "starter_code": "def reverse_string(s):\n    # Write your code here\n    pass",
        "reference_solution": "def reverse_string(s):\n    return s[::-1]",
        "tests": [
            {"input": "hello", "expected": "olleh", "visibility": "public"},
            {"input": "", "expected": "", "visibility": "private"},
            {"input": "a", "expected": "a", "visibility": "private"},
            {"input": "12345", "expected": "54321", "visibility": "private"},
        ],
        "max_time_ms": 2000,
        "max_memory_kb": 256000,
    }