"""Simple template: reverse string.

Includes reference solution and tests; can be validated locally.
"""

from __future__ import annotations

from typing import List, Dict


def template_reverse_string() -> Dict[str, object]:
    prompt_md = (
        "Write a program that reads a single line from standard input and\n"
        "prints the reversed string.\n\n"
        "Example:\n"
        "Input: hello\n"
        "Output: olleh\n"
    )
    starter_code = (
        "# Read from stdin and print the reversed string\n"
        "s = input().rstrip()\n"
        "# TODO: implement\n"
        "print(s)\n"
    )
    reference_solution = (
        "s = input().rstrip()\n"
        "print(s[::-1])\n"
    )
    tests: List[Dict[str, str]] = [
        {"input": "hello\n", "expected": "olleh\n", "visibility": "public"},
        {"input": "abc\n", "expected": "cba\n", "visibility": "public"},
        {"input": "racecar\n", "expected": "racecar\n", "visibility": "hidden"},
        {"input": "A man a plan a canal\n", "expected": "lanac a nalp a nam A\n", "visibility": "hidden"},
    ]
    return {
        "prompt_md": prompt_md,
        "starter_code": starter_code,
        "reference_solution": reference_solution,
        "tests": tests,
        "language_id": 71,  # Python (3.8+ in Judge0), can be adjusted
        "max_time_ms": 2000,
        "max_memory_kb": 128000,
        "points": 1,
        "tier": "bronze",
    }

