import requests


OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "llama3.2:1b"


def ask_ollama(prompt):

    data = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 300
        }
    }

    response = requests.post(
        OLLAMA_URL,
        json=data,
        timeout=120
    )

    if response.status_code == 200:

        result = response.json()

        return result.get(
            "response",
            "No response generated."
        )

    else:

        return (
            f"Ollama error: "
            f"{response.status_code}"
        )