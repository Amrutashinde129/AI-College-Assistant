import streamlit as st
from utils.ollama_client import ask_ollama


def answer_question(vector_store, question):

    documents = vector_store.similarity_search(
        question,
        k=5
    )

    # DEBUG: show what FAISS retrieved
    st.write("### 🔍 Retrieved document content")

    if not documents:
        st.error("FAISS returned 0 documents.")
        return "No relevant content was retrieved."

    for i, document in enumerate(documents):
        st.write(f"**Chunk {i + 1}:**")
        st.write(document.page_content)

    context = "\n\n".join(
        document.page_content
        for document in documents
    )

    prompt = f"""
You are an AI College Assistant.

Use ONLY the information in the following college notes.

COLLEGE NOTES:
{context}

QUESTION:
{question}

Answer the question clearly and directly.

If the answer is genuinely not present in the notes, say:
"This information is not available in the uploaded document."
"""

    return ask_ollama(prompt)