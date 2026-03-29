import os
import ollama

from config import get_ollama_base_url, get_groq_api_key, get_groq_model

_selected_model: str | None = None


def _use_groq() -> bool:
    return bool(os.environ.get("GROQ_API_KEY") or get_groq_api_key())


def _groq_key() -> str:
    return os.environ.get("GROQ_API_KEY") or get_groq_api_key()


def _client() -> ollama.Client:
    return ollama.Client(host=get_ollama_base_url())


def list_models() -> list[str]:
    if _use_groq():
        return ["llama-3.3-70b-versatile", "llama3-8b-8192", "mixtral-8x7b-32768"]
    response = _client().list()
    return sorted(m.model for m in response.models)


def select_model(model: str) -> None:
    global _selected_model
    _selected_model = model


def get_active_model() -> str | None:
    return _selected_model


def generate_text(prompt: str, model_name: str = None) -> str:
    if _use_groq():
        from groq import Groq
        client = Groq(api_key=_groq_key())
        response = client.chat.completions.create(
            model=get_groq_model(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
        )
        return response.choices[0].message.content.strip()

    # Ollama fallback
    model = model_name or _selected_model
    if not model:
        raise RuntimeError(
            "No Ollama model selected. Call select_model() first or pass model_name."
        )
    response = _client().chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"].strip()
