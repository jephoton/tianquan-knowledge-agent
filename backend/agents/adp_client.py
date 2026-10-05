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
           https://cloud.tencent.com/document/product/1759/129202
Endpoint: https://wss.lke.tencentcloud.com/adp/v2/chat
"""

from __future__ import annotations

import json
import os
import ssl
import uuid

import requests
from requests.adapters import HTTPAdapter

ADP_URL = "https://wss.lke.tencentcloud.com/adp/v2/chat"
DEFAULT_TIMEOUT = 60


def _uuid() -> str:
    """Return a UUID string (no dashes) that fits ADP's 32-64 char regex."""
    return uuid.uuid4().hex


class _SSLContextAdapter(HTTPAdapter):
    """requests adapter that uses a caller-supplied SSLContext."""

    def __init__(self, ssl_context: ssl.SSLContext, **kwargs):
        self._ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self._ssl_context
        return super().init_poolmanager(*args, **kwargs)


def _build_session() -> requests.Session:
    """Return a requests Session that trusts the OS certificate store.

    On networks that perform TLS interception (corporate proxy / VPN /
    antivirus), the intercepting CA is installed in the operating system
    trust store but NOT in certifi's bundle — which is why the default
    requests call fails with CERTIFICATE_VERIFY_FAILED. `truststore` bridges
    Python's TLS to the OS store, fixing that. Falls back to certifi, then
    to the stock session, if truststore is unavailable.
    """
    session = requests.Session()
    try:
        import truststore
        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        session.mount("https://", _SSLContextAdapter(ctx))
    except Exception:
        # truststore not available — leave the default (certifi) session.
        # The orchestrator still falls back to the stub if the call fails.
        pass
    return session


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
        visitor_id: str = "tianquan-user",
    ):
        self._app_key = app_key or os.environ.get("ADP_APP_KEY", "")
        self._timeout = timeout
        self._visitor_id = visitor_id
        self._conversation_id = _uuid()
        self._session = _build_session()

        if not self._app_key:
            raise RuntimeError(
                "ADP_APP_KEY not set. Set the environment variable or "
                "fall back to StubLLMClient for offline use."
            )

    def generate(self, prompt: str) -> str:
        """Call the ADP Chat API and return the accumulated answer text.

        The prompt is sent in the official ADP `Contents` array. The API
        returns SSE events; we accumulate all text delta/replace events.
        """
        headers = {
            "Content-Type": "application/json",
        }
        payload = {
            "RequestId": _uuid(),
            "ConversationId": self._conversation_id,
            "AppKey": self._app_key,
            "VisitorId": self._visitor_id,
            "UserId": self._visitor_id,
            "Contents": [
                {"Type": "text", "Text": prompt},
            ],
            "Incremental": True,
            "Stream": "enable",
        }

        resp = self._session.post(
            ADP_URL,
            headers=headers,
            json=payload,
            timeout=self._timeout,
            stream=True,
        )
        resp.raise_for_status()

        # Accumulate text from SSE events.
        # Official ADP events carry answer text in `Text` (capital T) on
        # `text.delta` / `text.replace` events.
        text_parts: list[str] = []
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data:"):
                data_str = line[5:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                event_type = event.get("Type", "")
                if event_type in ("text.delta", "text.replace"):
                    text = event.get("Text", "")
                    if isinstance(text, str) and text:
                        text_parts.append(text)

        return "".join(text_parts) or "No response from ADP agent."