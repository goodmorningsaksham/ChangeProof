"""Shared LLM client helper for ChangeProof agentic reasoning calls.

Implements OpenAI -> Anthropic -> None fallback chain.
Callers receive the raw text response and handle parsing themselves.
All calls use temperature=0.0 for deterministic structured-output prompts.
"""
import os
import re
import json
from typing import Optional


def call_llm(prompt: str, max_tokens: int = 1024) -> Optional[str]:
    """Makes a single LLM call with the given prompt.

    Tries providers in order:
      1. OpenAI (gpt-4o-mini) if OPENAI_API_KEY is set
      2. Anthropic (claude-3-5-haiku-latest) if ANTHROPIC_API_KEY is set
      3. Returns None if no provider is available

    Args:
        prompt: The full user-role prompt text.
        max_tokens: Maximum tokens in the response.

    Returns:
        Response text from the LLM, or None if no provider succeeded.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if openai_key:
        try:
            import openai
            oa_client = openai.OpenAI(api_key=openai_key)
            oa_resp = oa_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=max_tokens,
            )
            return oa_resp.choices[0].message.content or ""
        except Exception:
            pass

    if anthropic_key:
        try:
            import anthropic
            anth_client = anthropic.Anthropic(api_key=anthropic_key)
            anth_resp = anth_client.messages.create(
                model="claude-3-5-haiku-latest",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            content_block = anth_resp.content[0]
            return str(getattr(content_block, "text", ""))
        except Exception:
            pass

    return None


def parse_json_response(response_text: str) -> dict:
    """Strips markdown fences and parses JSON from an LLM response.

    Args:
        response_text: Raw LLM response, possibly wrapped in ```json ... ```.

    Returns:
        Parsed dict, or empty dict on parse failure.
    """
    clean = response_text.strip()
    if clean.startswith("```"):
        import re as _re
        clean = _re.sub(r"^```(?:json)?\n?", "", clean)
        clean = _re.sub(r"\n?```$", "", clean)
    try:
        return json.loads(clean.strip())
    except Exception:
        return {}
