"""Shared LLM client helper for ChangeProof agentic reasoning calls.

Implements fallback chain:
  1. Google Gemini (gemini-2.5-flash / gemini-2.5-flash-lite / gemini-2.0-flash / gemini-1.5-flash) with 429 retry
  2. OpenAI (gpt-4o-mini)
  3. Anthropic (claude-3-5-haiku-latest)
  4. Returns None (caller falls back to deterministic/template logic)

All calls use temperature=0.0 for deterministic structured-output prompts.
"""
import os
import re
import json
import time
from typing import Optional


def _load_env_if_needed():
    """Loads .env from project root or current working directory if keys not in environ."""
    for candidate in [".env", os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")]:
        if os.path.exists(candidate):
            for enc in ["utf-8-sig", "utf-8", "utf-16"]:
                try:
                    with open(candidate, "r", encoding=enc) as f:
                        for line in f.read().splitlines():
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                k, v = line.split("=", 1)
                                if k.strip() not in os.environ:
                                    os.environ[k.strip()] = v.strip()
                    break
                except Exception:
                    continue


def call_llm(prompt: str, max_tokens: int = 2048) -> Optional[str]:
    """Makes a single LLM call with the given prompt following the fallback chain.

    Args:
        prompt: The full user prompt.
        max_tokens: Maximum tokens in response.

    Returns:
        The raw response string from the model, or None if all providers fail/unavailable.
    """
    _load_env_if_needed()

    # --- 1. Google Gemini ---
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)

            candidate_models = [
                "gemini-2.5-flash",
                "gemini-2.5-flash-lite",
                "gemini-2.0-flash",
                "gemini-1.5-flash",
            ]

            for model_name in candidate_models:
                for attempt in range(2):  # 1 initial + 1 retry on 429
                    try:
                        model = genai.GenerativeModel(model_name)
                        resp = model.generate_content(
                            prompt,
                            generation_config={"temperature": 0.0, "max_output_tokens": max_tokens},
                            request_options={"timeout": 20.0},
                        )
                        if resp and resp.text:
                            return resp.text
                    except Exception as ge:
                        err_str = str(ge).lower()
                        is_rate_limit = "429" in err_str or "quota" in err_str or "rate" in err_str or "resourceexhausted" in err_str
                        if is_rate_limit and attempt == 0:
                            print(f"[LLM] Gemini ({model_name}) rate limited (429/quota), retrying once after 1.5s...")
                            time.sleep(1.5)
                            continue
                        elif "not found" in err_str or "404" in err_str or "no longer available" in err_str:
                            break
                        else:
                            print(f"[LLM] Gemini ({model_name}) error: {ge}")
                            break
        except ImportError:
            print("[LLM] google-generativeai not installed, skipping Gemini provider.")
        except Exception as e:
            print(f"[LLM] Unexpected Gemini configuration error: {e}")

    # --- 2. OpenAI ---
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            import openai
            client = openai.OpenAI(timeout=20.0)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=max_tokens,
            )
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content
        except ImportError:
            print("[LLM] openai package not installed, skipping OpenAI provider.")
        except Exception as e:
            print(f"[LLM] OpenAI call failed: {e}")

    # --- 3. Anthropic ---
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(timeout=20.0)
            msg = client.messages.create(
                model="claude-3-5-haiku-latest",
                max_tokens=max_tokens,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
            )
            if msg.content:
                text_blocks = [b.text for b in msg.content if hasattr(b, "text")]
                if text_blocks:
                    return "".join(text_blocks)
        except ImportError:
            print("[LLM] anthropic package not installed, skipping Anthropic provider.")
        except Exception as e:
            print(f"[LLM] Anthropic call failed: {e}")

    # All providers exhausted / unavailable
    return None


def parse_json_response(raw_text: Optional[str]) -> Optional[dict]:
    """Extracts and parses JSON object or array from LLM response text."""
    if not raw_text:
        return None
    cleaned = raw_text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    if match:
        cleaned = match.group(1).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    match_obj = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
    if match_obj:
        try:
            return json.loads(match_obj.group(1))
        except Exception:
            pass
    return None
