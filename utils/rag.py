from utils.ollama_client import ask_ollama


def answer_question(vector_store, question):

    try:
        # Retrieve more relevant chunks
        documents = vector_store.similarity_search(
            question,
            k=5
        )

        if not documents:
            return "This information is not available in the uploaded document."

        context_parts = []

        for document in documents:
            text = document.page_content.strip()

            if text:
                context_parts.append(text)

        context = "\n\n---\n\n".join(context_parts)

        prompt = f"""
You are an AI College Assistant.

Answer the user's question using the college notes provided below.

COLLEGE NOTES:
{context}

USER QUESTION:
{question}

INSTRUCTIONS:
1. Carefully search all the provided college notes before answering.
2. Answer using information from the notes.
3. You may combine information from multiple sections of the notes.
4. Give a simple and clear answer.
5. Do not invent facts that are not present in the notes.
6. If the requested information genuinely cannot be found in the notes, say:
"This information is not available in the uploaded document."

ANSWER:
"""

        answer = ask_ollama(prompt)

        return answer

    except Exception as e:
        return f"❌ RAG error: {str(e)}"