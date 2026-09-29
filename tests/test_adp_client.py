"""Tests for the ADP (Agent Development Platform) LLM client adapter.

These tests verify that ADPClient correctly implements the LLMClient
protocol and handles the ADP Chat API SSE response format. HTTP calls
are mocked so tests run fully offline.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.agents.adp_client import ADPClient
from backend.agents.llm_client import LLMClient


class _FakeSSEResponse:
    """Mimic a requests.Response with iter_lines for SSE streaming."""

    def __init__(self, lines: list[str], status_code: int = 200):
        self._lines = lines
        self.status_code = status_code

    def iter_lines(self, decode_unicode=True):
        for line in self._lines:
            yield line

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def test_adp_client_implements_protocol():
    """ADPClient should satisfy the LLMClient protocol."""
    client = ADPClient(app_key="fake-key")
    assert isinstance(client, LLMClient)


def test_adp_client_requires_app_key():
    """Without an AppKey, construction should fail."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError, match="ADP_APP_KEY"):
            ADPClient(app_key=None)


def test_adp_client_generate_accumulates_sse_text():
    """generate() should accumulate text from SSE data events."""
    client = ADPClient(app_key="fake-key")

    sse_lines = [
        'data: {"type": "text", "data": "Based on the "}',
        'data: {"type": "text", "data": "available sources, "}',
        'data: {"type": "text", "data": "here is the answer."}',
        "",
    ]
    fake_resp = _FakeSSEResponse(sse_lines)

    with patch("backend.agents.adp_client.requests.post", return_value=fake_resp):
        result = client.generate("Summarize the migration plan.")

    assert result == "Based on the available sources, here is the answer."


def test_adp_client_generate_handles_empty_response():
    """generate() should return a fallback message if no text is received."""
    client = ADPClient(app_key="fake-key")

    fake_resp = _FakeSSEResponse([])

    with patch("backend.agents.adp_client.requests.post", return_value=fake_resp):
        result = client.generate("What is the DB migration plan?")

    assert "No response" in result


def test_adp_client_generate_sends_appkey():
    """generate() should send the AppKey in the Authorization header."""
    client = ADPClient(app_key="test-appkey")

    fake_resp = _FakeSSEResponse([
        'data: {"data": "ok"}',
    ])

    with patch("backend.agents.adp_client.requests.post", return_value=fake_resp) as mock_post:
        client.generate("test prompt")

    call_args = mock_post.call_args
    headers = call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer test-appkey"

    payload = call_args.kwargs["json"]
    assert payload["content"][0]["type"] == "text"
    assert payload["content"][0]["data"] == "test prompt"