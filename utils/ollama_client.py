```python
import os
import requests

HF_API_URL = "https://api-inference.huggingface.co/models/google/flan-t5-base"


def ask_ollama(prompt):
    """
    Generates a response using Hugging Face.
    Function name is kept as ask_ollama so existing project
    files do not need to be changed.
    """

    api_key = os.getenv("HF_TOKEN")

    if not api_key:
        return "Hugging Face API token is not configured."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "inputs": prompt,
        "parameters": {
            "temperature": 0.2,
            "max_new_tokens": 300
        }
    }

    try:
        response = requests.post(
            HF_API_URL,
            headers=headers,
            json=data,
            timeout=120
        )

        if response.status_code == 200:
            result = response.json()

            if isinstance(result, list) and len(result) > 0:
                return result[0].get(
                    "generated_text",
                    "No response generated."
                )

            return "No response generated."

        return f"Hugging Face error: {response.status_code} - {response.text}"

    except requests.exceptions.Timeout:
        return "Hugging Face request timed out."

    except requests.exceptions.ConnectionError:
        return "Could not connect to Hugging Face."

    except Exception as e:
        return f"Error generating response: {str(e)}"
```
