from utils.ollama_client import ask_ollama


def answer_question(vector_store, question):

    documents = vector_store.similarity_search(
        question,
        k=3
    )

    context_parts = []

    for document in documents:

        text = document.page_content[:1500]

        context_parts.append(text)

    context = "\n\n".join(context_parts)

    prompt = f"""
You are an AI College Assistant.

Answer the question using the provided college notes.

College Notes:
{context}

Question:
{question}

Rules:
- Give a simple and direct answer.
- Use only the provided notes.
- Do not invent information.
- If the answer is not in the notes, say:
"This information is not available in the uploaded document."
"""

    return ask_ollama(prompt)