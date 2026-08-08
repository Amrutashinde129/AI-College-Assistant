import streamlit as st
from huggingface_hub import InferenceClient


MODEL_NAME = "mistralai/Mistral-7B-Instruct-v0.2"


def ask_ollama(prompt):

    try:
        token = st.secrets["HF_TOKEN"]

        client = InferenceClient(
            model=MODEL_NAME,
            token=token
        )

        response = client.chat_completion(
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=300,
            temperature=0.2
        )

        return response.choices[0].message.content

    except KeyError:
        return "Hugging Face API token is not configured."

    except Exception as e:
        return f"Hugging Face error: {str(e)}"
