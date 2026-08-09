import streamlit as st
from google import genai

MODEL_NAME = "gemini-3.6-flash"


def ask_ollama(prompt):

    try:
        api_key = st.secrets["GEMINI_API_KEY"]

        client = genai.Client(
            api_key=api_key
        )

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )

        if response.text:
            return response.text

        return "❌ Gemini returned an empty response."

    except KeyError:
        return (
            "❌ GEMINI_API_KEY is not configured. "
            "Please add it to Streamlit Secrets."
        )

    except Exception as e:
        return f"❌ Gemini error: {str(e)}"