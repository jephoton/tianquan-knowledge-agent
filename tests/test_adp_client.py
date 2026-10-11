"""Tests for the ADP (Agent Development Platform) LLM client adapter.

These tests verify that ADPClient correctly implements the LLMClient
protocol and handles the Tencent Cloud ADP Chat API SSE response format.
HTTP calls are mocked so tests run fully offline.

Reference: https://cloud.tencent.com/document/product/1759/129202
"""

from __future__ import annotations

from unittest.mock import patch

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


def test_adp_client_generate_accumulates_text_delta_events():
    """generate() should accumulate text from official ADP text.delta events."""
    client = ADPClient(app_key="fake-key", visitor_id="visitor-1")

    sse_lines = [
        'data: {"Type": "text.delta", "Text": "Based on the "}',
        'data: {"Type": "text.delta", "Text": "available sources, "}',
        'data: {"Type": "text.delta", "Text": "here is the answer."}',
        "",
    ]
    fake_resp = _FakeSSEResponse(sse_lines)

    with patch.object(client._session, "post", return_value=fake_resp):
        result = client.generate("Summarize the migration plan.")

    assert result == "Based on the available sources, here is the answer."


def test_adp_client_generate_handles_text_replace_events():
    """generate() should also handle text.replace events."""
    client = ADPClient(app_key="fake-key")

    sse_lines = [
        'data: {"Type": "text.replace", "Text": "Replacement answer."}',
    ]
    fake_resp = _FakeSSEResponse(sse_lines)

    with patch.object(client._session, "post", return_value=fake_resp):
        result = client.generate("What is the DB migration plan?")

    assert result == "Replacement answer."


def test_adp_client_generate_handles_empty_response():
    """generate() should return a fallback message if no text is received."""
    client = ADPClient(app_key="fake-key")

    fake_resp = _FakeSSEResponse([])

    with patch.object(client._session, "post", return_value=fake_resp):
        result = client.generate("What is the DB migration plan?")

    assert "No response" in result


def test_adp_client_generate_sends_official_payload():
    """generate() should send the official ADP request body format."""
    client = ADPClient(app_key="test-appkey", visitor_id="visitor-42")

    fake_resp = _FakeSSEResponse([
        'data: {"Type": "text.delta", "Text": "ok"}',
    ])

    with patch.object(client._session, "post", return_value=fake_resp) as mock_post:
        client.generate("test prompt")

    call_args = mock_post.call_args
    headers = call_args.kwargs["headers"]
    assert "Authorization" not in headers

    payload = call_args.kwargs["json"]
    assert payload["AppKey"] == "test-appkey"
    assert payload["VisitorId"] == "visitor-42"
    assert payload["UserId"] == "visitor-42"
    assert "ConversationId" in payload
    assert "RequestId" in payload
    assert payload["Contents"][0]["Type"] == "text"
    assert payload["Contents"][0]["Text"] == "test prompt"
    assert payload["Stream"] == "enable"

class _Latin1DefaultResponse(_FakeSSEResponse):
    """Like requests for a text/event-stream with no charset: the body is UTF-8
    bytes, but `encoding` defaults to ISO-8859-1 and iter_lines(decode_unicode)
    decodes with it — turning "—" into "â€”" unless the client sets UTF-8."""

    def __init__(self, lines):
        super().__init__(lines)
        self.encoding = "ISO-8859-1"

    def iter_lines(self, decode_unicode=True):
        for line in self._lines:
            yield line.encode("utf-8").decode(self.encoding)


def test_adp_client_decodes_stream_as_utf8():
    client = ADPClient(app_key="fake-key")
    fake_resp = _Latin1DefaultResponse([
        'data: {"Type": "text.delta", "Text": "cluster — resolved. 天权"}',
    ])
    with patch.object(client._session, "post", return_value=fake_resp):
        assert client.generate("q") == "cluster — resolved. 天权"


def test_each_generate_call_uses_a_fresh_conversation():
    """One ADPClient serves every user's query in the API process. Reusing an
    ADP ConversationId would give the model memory of earlier prompts — i.e.
    a previous user's authorized context — breaking INV2 (the model sees only
    the current asker's filtered context). Every call must be stateless."""
    client = ADPClient(app_key="fake-key")
    ok = 'data: {"Type": "text.delta", "Text": "x"}'
    with patch.object(client._session, "post",
                      side_effect=lambda *a, **k: _FakeSSEResponse([ok])) as mock_post:
        client.generate("alice's authorized context")
        client.generate("charlie's authorized context")
    ids = [c.kwargs["json"]["ConversationId"] for c in mock_post.call_args_list]
    assert len(ids) == 2 and ids[0] != ids[1]
