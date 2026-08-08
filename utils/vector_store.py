from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS


def create_vector_store(text):

    # Create embeddings using Hugging Face
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    # Split text into chunks
    chunks = []

    chunk_size = 1000
    overlap = 200

    start = 0

    while start < len(text):

        end = start + chunk_size

        chunk = text[start:end]

        if chunk.strip():
            chunks.append(chunk)

        start += chunk_size - overlap

    # Create FAISS vector database
    vector_store = FAISS.from_texts(
        chunks,
        embeddings
    )

    return vector_store
