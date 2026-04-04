"""
OpenRouter LLM Client — VÉLØ VOX Provider
==========================================
Wraps the OpenRouter API (https://openrouter.ai) using an OpenAI-compatible
interface. Reads credentials from environment variables.

Required env vars:
    OPENROUTER_API_KEY   — your OpenRouter API key (starts with sk-or-...)
    OPENROUTER_MODEL     — model slug, e.g. "anthropic/claude-3.5-sonnet"
                           Defaults to "anthropic/claude-3-haiku"

Optional env vars:
    OPENROUTER_SITE_URL  — your site URL (sent as HTTP-Referer header)
    OPENROUTER_SITE_NAME — your app name (sent as X-Title header)

Usage:
    client = OpenRouterClient()
    response = client.chat(
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=4096,
        temperature=0.3,
    )
    # response is a plain string
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

_OPENROUTER_BASE = "https://openrouter.ai/api/v1/chat/completions"

# Default model — fast and cheap; override via OPENROUTER_MODEL env var
_DEFAULT_MODEL = "anthropic/claude-3-haiku"


class OpenRouterClient:
    """
    Minimal, dependency-free OpenRouter client.
    Uses only stdlib (urllib) so it works in any environment without
    additional pip installs.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        site_url: str | None = None,
        site_name: str | None = None,
    ):
        self.api_key = (
            api_key
            or os.getenv("OPENROUTER_API_KEY", "")
            or os.getenv("ANTHROPIC_API_KEY", "")  # fallback
        )
        self.model = model or os.getenv("OPENROUTER_MODEL", _DEFAULT_MODEL)
        self.site_url = site_url or os.getenv("OPENROUTER_SITE_URL", "https://velo-oracle.app")
        self.site_name = site_name or os.getenv("OPENROUTER_SITE_NAME", "VELO Oracle")

        if not self.api_key:
            logger.warning(
                "[OpenRouterClient] OPENROUTER_API_KEY not set — "
                "chat() will return an error message instead of a real response."
            )

    # ── Public API ─────────────────────────────────────────────────────────────

    def chat(
        self,
        messages: list[dict],
        max_tokens: int = 4096,
        temperature: float = 0.3,
        model: str | None = None,
    ) -> str:
        """
        Send a chat completion request to OpenRouter.

        Args:
            messages:    List of {"role": ..., "content": ...} dicts.
                         Must include at least one message.
            max_tokens:  Maximum tokens in the response.
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative).
            model:       Override the instance-level model for this call only.

        Returns:
            The assistant's reply as a plain string.
            On any error, returns a descriptive error string (never raises).
        """
        if not self.api_key:
            return (
                "[VELO Agent] LLM provider not configured. "
                "Set OPENROUTER_API_KEY in environment variables."
            )

        target_model = model or self.model

        payload = {
            "model": target_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": self.site_url,
            "X-Title": self.site_name,
        }

        try:
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                _OPENROUTER_BASE,
                data=body,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)

            # Standard OpenAI-compatible response shape
            choices = data.get("choices", [])
            if not choices:
                logger.error("[OpenRouterClient] Empty choices in response: %s", raw[:500])
                return "[VELO Agent] Empty response from LLM provider."

            content = choices[0].get("message", {}).get("content", "")
            if not content:
                logger.error("[OpenRouterClient] Empty content in response: %s", raw[:500])
                return "[VELO Agent] LLM returned empty content."

            return content

        except urllib.error.HTTPError as e:
            body_text = ""
            try:
                body_text = e.read().decode("utf-8")[:500]
            except Exception:
                pass
            logger.error(
                "[OpenRouterClient] HTTP %d from OpenRouter: %s", e.code, body_text
            )
            return (
                f"[VELO Agent] LLM provider error (HTTP {e.code}). "
                f"Check OPENROUTER_API_KEY and model name '{target_model}'."
            )

        except urllib.error.URLError as e:
            logger.error("[OpenRouterClient] Network error: %s", e.reason)
            return f"[VELO Agent] Network error reaching LLM provider: {e.reason}"

        except Exception as e:
            logger.exception("[OpenRouterClient] Unexpected error in chat()")
            return f"[VELO Agent] Unexpected error: {e}"

    # ── Convenience helpers ────────────────────────────────────────────────────

    def complete(self, prompt: str, **kwargs) -> str:
        """Single-turn completion helper. Wraps prompt in a user message."""
        return self.chat(
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )

    def model_info(self) -> dict:
        """Return current configuration (no API call)."""
        return {
            "model": self.model,
            "api_key_set": bool(self.api_key),
            "site_url": self.site_url,
            "site_name": self.site_name,
        }
