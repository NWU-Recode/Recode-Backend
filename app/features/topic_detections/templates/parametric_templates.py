"""
Parametric templates for question generation.
"""

def generate_question_template(difficulty: str, topic: str, question_type: str) -> str:
    """
    Generate a question template based on parameters.
    :param difficulty: The difficulty level of the question (e.g., easy, medium, hard).
    :param topic: The topic of the question.
    :param question_type: The type of question (e.g., multiple-choice, open-ended).
    :return: A formatted question template.
    """
    if question_type == "multiple-choice":
        return f"Create a {difficulty} multiple-choice question on the topic of {topic}. Include 4 options and specify the correct answer."
    elif question_type == "open-ended":
        return f"Create a {difficulty} open-ended question on the topic of {topic}. Provide a detailed answer key."
    else:
        return f"Create a {difficulty} question on the topic of {topic}. Specify the question type as {question_type}."

# Example usage
if __name__ == "__main__":
    print(generate_question_template("easy", "Python Basics", "multiple-choice"))
    print(generate_question_template("hard", "Data Structures", "open-ended"))
