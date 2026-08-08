from utils.ollama_client import ask_ollama


def generate_mcqs(text, number_of_questions=5):

    prompt = f"""
You are an AI College Assistant.

Generate {number_of_questions} multiple-choice
questions from the following college study material.

Study Material:
{text}

For every question provide:

Question:
A)
B)
C)
D)
Correct Answer:
Explanation:

Rules:
- Use only information from the study material.
- Make the questions suitable for college students.
- Avoid duplicate questions.
- Provide four options for every question.
- Clearly identify the correct answer.
- Give a short explanation.
"""

    return ask_ollama(prompt)