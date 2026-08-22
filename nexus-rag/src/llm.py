"""
LLM abstraction. Swap providers by changing LLM_PROVIDER in .env —
no other file needs to change.
Supported: gemini, groq, xai (Grok), openai, ollama

xai/openai share one implementation because xAI's API is OpenAI-compatible; the
only difference is the base URL. LLM_BASE_URL can point either at any other
OpenAI-compatible endpoint (OpenRouter, Together, a local vLLM server).
"""
from src.config import (LLM_PROVIDER, LLM_API_KEY, LLM_MODEL, OLLAMA_BASE_URL,
                        LLM_BASE_URL)

XAI_BASE_URL = "https://api.x.ai/v1"


class LLMError(Exception):
    pass


_KEY_PREFIXES = {"gsk_": "groq", "AIza": "gemini", "xai-": "xai", "sk-": "openai"}


def _key_mismatch_hint() -> str:
    """
    The commonest setup mistake is a key from one provider with LLM_PROVIDER set
    to another. Key prefixes identify the issuer, so say so plainly.
    """
    for prefix, provider in _KEY_PREFIXES.items():
        if LLM_API_KEY.startswith(prefix) and provider != LLM_PROVIDER:
            return (f" Your key starts with '{prefix}', which is a {provider} key, "
                    f"but LLM_PROVIDER is '{LLM_PROVIDER}'. "
                    f"Set LLM_PROVIDER={provider} in .env and restart.")
    return ""


def generate(system_prompt: str, user_prompt: str) -> str:
    """Route to the configured provider. Raises LLMError on failure."""
    hint = _key_mismatch_hint()
    if hint:
        raise LLMError(f"LLM provider and API key do not match.{hint}")
    try:
        if LLM_PROVIDER == "gemini":
            return _generate_gemini(system_prompt, user_prompt)
        elif LLM_PROVIDER == "groq":
            return _generate_groq(system_prompt, user_prompt)
        elif LLM_PROVIDER == "openai":
            return _generate_openai(system_prompt, user_prompt)
        elif LLM_PROVIDER in ("xai", "grok"):
            return _generate_openai(system_prompt, user_prompt,
                                     base_url=LLM_BASE_URL or XAI_BASE_URL,
                                     default_model="grok-2-latest",
                                     label="xAI (Grok)")
        elif LLM_PROVIDER == "ollama":
            return _generate_ollama(system_prompt, user_prompt)
        else:
            raise LLMError(f"Unknown LLM_PROVIDER '{LLM_PROVIDER}'. "
                            f"Use one of: gemini, groq, xai, openai, ollama.")
    except LLMError:
        raise
    except Exception as e:
        raise LLMError(f"{LLM_PROVIDER} request failed: {e}")


def _generate_gemini(system_prompt: str, user_prompt: str) -> str:
    if not LLM_API_KEY:
        raise LLMError("LLM_API_KEY is not set for Gemini. Add a key to .env "
                        "(https://aistudio.google.com/apikey), or set LLM_PROVIDER=groq "
                        "if you have a Groq key.")
    import google.generativeai as genai
    genai.configure(api_key=LLM_API_KEY)
    model = genai.GenerativeModel(model_name=LLM_MODEL, system_instruction=system_prompt)
    response = model.generate_content(user_prompt)
    return (response.text or "").strip()


def _generate_groq(system_prompt: str, user_prompt: str) -> str:
    if not LLM_API_KEY:
        raise LLMError("LLM_API_KEY is not set for Groq. Add a key to .env "
                        "(https://console.groq.com/keys).")
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


def _generate_openai(system_prompt: str, user_prompt: str, base_url: str = None,
                      default_model: str = "gpt-4o-mini", label: str = "OpenAI") -> str:
    if not LLM_API_KEY:
        raise LLMError(f"LLM_API_KEY is not set for {label}.")
    from openai import OpenAI
    client = OpenAI(api_key=LLM_API_KEY, base_url=base_url or (LLM_BASE_URL or None))
    completion = client.chat.completions.create(
        model=LLM_MODEL or default_model,
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
