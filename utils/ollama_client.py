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

        return "No response was generated."

    except KeyError:
        return "❌ GEMINI_API_KEY is not configured."

    except Exception as e:
        error = str(e)

        if "429" in error or "RESOURCE_EXHAUSTED" in error:
            return (
                "⚠️ Gemini API quota has been reached. "
                "Please try again later."
            )

        return f"❌ Gemini error: {error}"