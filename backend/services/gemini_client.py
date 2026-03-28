"""
Gemini API client wrapper using the google-genai SDK.

The athlete's API key is decrypted at call time — never stored globally.
Calls are wrapped in run_in_executor to avoid blocking the event loop.
"""
import asyncio
import functools
import logging

logger = logging.getLogger(__name__)


def _call_gemini_sync(
    prompt: str,
    api_key: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
    )
    return response.text


async def call_gemini(
    prompt: str,
    api_key: str,
    model: str | None = None,
    temperature: float = 0.6,
    max_tokens: int = 256,
) -> str:
    """
    Send a prompt to Gemini and return the text response.
    Raises ValueError on auth failure, RuntimeError on quota exceeded.
    """
    from config import settings

    model_name = model or settings.GEMINI_PRIMARY_MODEL

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(
            None,
            functools.partial(_call_gemini_sync, prompt, api_key, model_name, temperature, max_tokens),
        )
    except Exception as exc:
        err = str(exc).lower()
        if any(w in err for w in ("api_key", "invalid", "unauthorized", "unauthenticated", "api key")):
            raise ValueError(f"Gemini auth failed: {exc}") from exc
        if any(w in err for w in ("quota", "rate", "429", "resource_exhausted")):
            raise RuntimeError(f"Gemini rate/quota limit: {exc}") from exc
        raise
