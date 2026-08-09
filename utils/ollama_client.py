import streamlit as st
from google import genai

MODEL_NAME = "gemini-3.5-flash"

def ask_ollama(prompt):

```
try:
    api_key = st.secrets["GEMINI_API_KEY"]

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt
    )

    return response.text

except KeyError:
    return "Gemini API key is not configured."

except Exception as e:
    return f"Gemini error: {str(e)}"
```
