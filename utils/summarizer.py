from utils.ollama_client import ask_ollama


def summarize_text(text):

    # Limit the amount of text sent to Ollama
    max_chars = 12000

    text = text[:max_chars]

    prompt = f"""
You are an AI College Assistant.

Create concise study notes from the following
college material.

College Material:
{text}

Use this format:

## 📚 Topic Overview

## 🔑 Important Concepts

## 📖 Key Definitions

## ⭐ Important Points

## 💡 Examples

## 📝 Quick Revision

Rules:
- Use simple language.
- Use bullet points.
- Keep the answer concise.
- Use ONLY the provided material.
- Do not invent information.
"""

    return ask_ollama(prompt)