"""
LLM abstraction. Swap providers by changing LLM_PROVIDER in .env —
no other file needs to change.
Supported: gemini, groq, openai, ollama
"""
from src.config import LLM_PROVIDER, LLM_API_KEY, LLM_MODEL, OLLAMA_BASE_URL


class LLMError(Exception):
    pass


def generate(system_prompt: str, user_prompt: str) -> str:
    """Route to the configured provider. Raises LLMError on failure."""
    try:
        if LLM_PROVIDER == "gemini":
            return _generate_gemini(system_prompt, user_prompt)
        elif LLM_PROVIDER == "groq":
            return _generate_groq(system_prompt, user_prompt)
        elif LLM_PROVIDER == "openai":
            return _generate_openai(system_prompt, user_prompt)
        elif LLM_PROVIDER == "ollama":
            return _generate_ollama(system_prompt, user_prompt)
        else:
            raise LLMError(f"Unknown LLM_PROVIDER '{LLM_PROVIDER}'. "
                            f"Use one of: gemini, groq, openai, ollama.")
    except LLMError:
        raise
    except Exception as e:
        raise LLMError(f"{LLM_PROVIDER} request failed: {e}")


def _generate_gemini(system_prompt: str, user_prompt: str) -> str:
    if not LLM_API_KEY:
        raise LLMError("LLM_API_KEY is not set. Get a free key at https://aistudio.google.com/apikey "
                        "and add it to your .env file.")
    import google.generativeai as genai
    genai.configure(api_key=LLM_API_KEY)
    model = genai.GenerativeModel(model_name=LLM_MODEL, system_instruction=system_prompt)
    response = model.generate_content(user_prompt)
    return (response.text or "").strip()


def _generate_groq(system_prompt: str, user_prompt: str) -> str:
    if not LLM_API_KEY:
        raise LLMError("LLM_API_KEY is not set for Groq.")
    from groq import Groq
    client = Groq(api_key=LLM_API_KEY)
    completion = client.chat.completions.create(
        model=LLM_MODEL or "llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return completion.choices[0].message.content.strip()


def _generate_openai(system_prompt: str, user_prompt: str) -> str:
    if not LLM_API_KEY:
        raise LLMError("LLM_API_KEY is not set for OpenAI.")
    from openai import OpenAI
    client = OpenAI(api_key=LLM_API_KEY)
    completion = client.chat.completions.create(
        model=LLM_MODEL or "gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return completion.choices[0].message.content.strip()


def _generate_ollama(system_prompt: str, user_prompt: str) -> str:
    import requests
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json={
            "model": LLM_MODEL or "llama3.1",
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()
