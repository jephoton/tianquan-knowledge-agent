"""Tencent Hunyuan LLM client adapter.

Implements the LLMClient protocol by calling the Hunyuan OpenAI-compatible
chat completions endpoint. The answer agent depends on the interface, never
on this concrete adapter (ADR-0005), so the permission-safety guarantee is
unaffected by the model choice.

Usage:
    Set HUNYUAN_API_KEY environment variable, then pass HunyuanLLMClient() to
    the Orchestrator instead of StubLLMClient().

    export HUNYUAN_API_KEY="your-key-here"

If the key is missing or the call fails, the client raises — the orchestrator
should be constructed with StubLLMClient() as fallback for offline/dev use.
"""

from __future__ import annotations

import os

import requests

HUNYUAN_URL = "https://api.hunyuan.cloud.tencent.com/v1/chat/completions"
HUNYUAN_MODEL = "hunyuan-turbos-latest"
DEFAULT_TIMEOUT = 30


class HunyuanLLMClient:
    """LLM client backed by Tencent Hunyuan's OpenAI-compatible API.

    The client receives a fully-assembled prompt whose context section
    already contains ONLY authorized content (filtered by the permission
    pipeline). The client must not fetch or invent additional content —
    it simply calls the model and returns the completion.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = HUNYUAN_MODEL,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self._api_key = api_key or os.environ.get("HUNYUAN_API_KEY", "")
        self._model = model
        self._timeout = timeout

        if not self._api_key:
            raise RuntimeError(
                "HUNYUAN_API_KEY not set. Set the environment variable or "
                "fall back to StubLLMClient for offline use."
            )
        self._headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

    def generate(self, prompt: str) -> str:
        """Call Hunyuan and return the model's completion text.

        The prompt is sent as a single user message. Temperature is kept
        low (0.3) for grounded, factual answers.
        """
        payload = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "enable_enhancement": False,
        }

        resp = requests.post(
            HUNYUAN_URL,
            headers=self._headers,
            json=payload,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]