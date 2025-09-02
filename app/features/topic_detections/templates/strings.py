# Stub for template_reverse_string to prevent import errors

def template_reverse_string():
    return {
        "language_id": 28,
        "starter_code": "def reverse_string(s):\n    return s[::-1]",
        "reference_solution": "def reverse_string(s):\n    return s[::-1]",
        "tests": [
            {"input": "hello", "expected": "olleh", "visibility": "public"},
            {"input": "world", "expected": "dlrow", "visibility": "private"}
        ],
        "max_time_ms": 2000,
        "max_memory_kb": 256000
    }
