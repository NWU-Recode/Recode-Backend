import hashlib
import re
from typing import Dict, Any, List, Optional

def generate_question_hash(question_data: Dict[str, Any]) -> str:
    """To generate a unique hash for a question based on its content"""
    content = f"{question_data.get('question_text', '')}"
    content += f"{question_data.get('expected_output', '')}"
    content += f"{question_data.get('starter_code', '')}"
    content += f"{question_data.get('tier', '')}"
    return hashlib.sha256(content.encode()).hexdigest()

def validate_question_tier(tier: str) -> bool:
    """Validate question difficulty tier"""
    valid_tiers = ["bronze", "silver", "gold", "ruby", "emerald", "diamond"]
    return tier.lower() in valid_tiers

def calculate_question_difficulty_score(tier: str) -> int:
    """Convert tier into numeric score"""
    tier_scores = {
        "bronze": 1, "silver": 2, "gold": 3,
        "ruby": 4, "emerald": 5, "diamond": 6
    }
    return tier_scores.get(tier.lower(), 1)

def extract_topics_from_text(text: str) -> List[str]:
    """Extract potential topics from question text"""
    common_topics = [
        "arrays", "lists", "strings", "loops", "recursion", "sorting",
        "searching", "dynamic programming", "graphs", "trees", "hash tables",
        "stacks", "queues", "linked lists", "algorithms", "data structures",
        "functions", "classes", "objects", "inheritance", "polymorphism"
    ]
    text_lower = text.lower()
    return [topic for topic in common_topics if topic in text_lower]

def format_execution_time(time_str: Optional[str]) -> str:
    """Format execution time string for display"""
    if not time_str:
        return "N/A"
    try:
        time_float = float(time_str)
        if time_float < 0.001:
            return f"{time_float * 1000:.3f}ms"
        elif time_float < 1:
            return f"{time_float * 1000:.1f}ms"
        else:
            return f"{time_float:.3f}s"
    except ValueError:
        return time_str

def format_memory_usage(memory_kb: Optional[int]) -> str:
    """Format memory usage for display"""
    if not memory_kb:
        return "N/A"
    if memory_kb < 1024:
        return f"{memory_kb} KB"
    return f"{memory_kb / 1024:.2f} MB"

def sanitize_code_input(code: str) -> str:
    """Sanitize code input to block dangerous patterns"""
    dangerous_patterns = [
        r'import\s+os', r'import\s+subprocess', r'import\s+sys',
        r'__import__', r'eval\s*\(', r'exec\s*\(', r'open\s*\('
    ]
    sanitized = code
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, '# BLOCKED', sanitized, flags=re.IGNORECASE)
    return sanitized

def validate_test_cases(test_cases: List[Dict[str, Any]]) -> List[str]:
    """Validate test cases format"""
    errors = []
    for i, test_case in enumerate(test_cases):
        if "input" not in test_case:
            errors.append(f"Test case {i+1}: Missing 'input'")
        if "expected_output" not in test_case:
            errors.append(f"Test case {i+1}: Missing 'expected_output'")
        if len(str(test_case.get("input", ""))) > 10000:
            errors.append(f"Test case {i+1}: Input too large")
        if len(str(test_case.get("expected_output", ""))) > 10000:
            errors.append(f"Test case {i+1}: Expected output too large")
    return errors
