"""Tencent Cloud ADP (Agent Development Platform) LLM client adapter.

Implements the LLMClient protocol by calling the ADP Chat API. The agent on
ADP handles model orchestration and knowledge base; Tianquan sends the
permission-filtered context as part of the question so the agent generates
a grounded answer using only authorized content.

The answer agent depends on the interface, never on this concrete adapter
(ADR-0005), so the permission-safety guarantee is unaffected by the model
choice. The LLM only ever receives already-filtered context (INV1/INV2).

Usage:
    Set ADP_APP_KEY environment variable, then the orchestrator auto-selects
    ADPClient. Without the key, StubLLMClient is used for offline/dev.

    export ADP_APP_KEY="your-appkey-from-adp-console"

Reference: docs/ADP_Hackathon_Guide_EN.pdf §6.2
Endpoint: https://wss.lke.tencentcloud.com/adp/v2/chat
"""

from __future__ import annotations

import json
import os

import requests

ADP_URL = "https://wss.lke.tencentcloud.com/adp/v2/chat"
DEFAULT_TIMEOUT = 60


class ADPClient:
    """LLM client backed by Tencent Cloud ADP Chat API.

    The client receives a fully-assembled prompt whose context section
    already contains ONLY authorized content (filtered by the permission
    pipeline). The client must not fetch or invent additional content —
    it sends the prompt to the ADP agent and returns the accumulated
    response text.

    The ADP API returns Server-Sent Events (SSE). This client accumulates
    all text chunks and returns the final concatenated answer.
    """

    def __init__(
        self,
        app_key: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self._app_key = app_key or os.environ.get("ADP_APP_KEY", "")
        self._timeout = timeout

        if not self._app_key:
            raise RuntimeError(
                "ADP_APP_KEY not set. Set the environment variable or "
                "fall back to StubLLMClient for offline use."
            )

    def generate(self, prompt: str) -> str:
        """Call the ADP Chat API and return the accumulated answer text.

        The prompt is sent as the 'question' field. The API returns SSE
        events; we accumulate all text content from the response.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._app_key}",
        }
        payload = {
            "content": [
                {"type": "text", "data": prompt},
            ],
        }

        resp = requests.post(
            ADP_URL,
            headers=headers,
            json=payload,
            timeout=self._timeout,
            stream=True,
        )
        resp.raise_for_status()

        # Accumulate text from SSE events.
        # The ADP API streams events; each event has a type and content.
        # We collect all text-bearing events and return the concatenation.
        text_parts: list[str] = []
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data:"):
                data_str = line[5:].strip()
                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                # ADP events may carry text in various fields.
                # The common patterns are:
                #   {"type": "text", "data": "..."}
                #   {"type": "message", "content": "..."}
                #   {"payload": {"text": "..."}}
                text = (
                    event.get("data")
                    or event.get("content")
                    or (event.get("payload") or {}).get("text")
                    or ""
                )
                if isinstance(text, str) and text:
                    text_parts.append(text)

        return "".join(text_parts) or "No response from ADP agent."