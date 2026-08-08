import streamlit as st
from huggingface_hub import InferenceClient


MODEL_NAME = "HuggingFaceH4/zephyr-7b-beta"


def ask_ollama(prompt):

    try:
        token = st.secrets["HF_TOKEN"]

        client = InferenceClient(
            model=MODEL_NAME,
            token=token
        )

        response = client.text_generation(
            prompt,
            max_new_tokens=300,
            temperature=0.2
        )

        return response

    except KeyError:
        return "Hugging Face API token is not configured."

    except Exception as e:
        return f"Hugging Face error: {str(e)}"
