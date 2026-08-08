import streamlit as st
from huggingface_hub import InferenceClient


MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"


def ask_ollama(prompt):

    try:
        token = st.secrets["HF_TOKEN"]

        client = InferenceClient(
            provider="hf-inference",
            api_key=token
        )

        response = client.chat_completion(
            model=MODEL_NAME,
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
