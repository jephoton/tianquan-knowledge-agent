"""Tests for the Hunyuan LLM client adapter.

These tests verify that HunyuanLLMClient correctly implements the LLMClient
protocol and handles the Hunyuan API response format. HTTP calls are mocked
so tests run fully offline.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.agents.hunyuan_client import HunyuanLLMClient
from backend.agents.llm_client import LLMClient


def test_hunyuan_client_implements_protocol():
    """HunyuanLLMClient should satisfy the LLMClient protocol."""
    client = HunyuanLLMClient(api_key="fake-key")
    assert isinstance(client, LLMClient)


def test_hunyuan_client_requires_api_key():
    """Without an API key, construction should fail."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError, match="HUNYUAN_API_KEY"):
            HunyuanLLMClient(api_key=None)


def test_hunyuan_client_generate_extracts_content():
    """generate() should extract the message content from the API response."""
    client = HunyuanLLMClient(api_key="fake-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {"message": {"role": "assistant", "content": "This is a grounded answer."}}
        ]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("backend.agents.hunyuan_client.requests.post", return_value=mock_resp):
        result = client.generate("Summarize the migration plan.")

    assert result == "This is a grounded answer."


def test_hunyuan_client_generate_sends_correct_payload():
    """generate() should send the prompt as a user message with low temperature."""
    client = HunyuanLLMClient(api_key="test-key")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "ok"}}]
    }
    mock_resp.raise_for_status = MagicMock()

    with patch("backend.agents.hunyuan_client.requests.post", return_value=mock_resp) as mock_post:
        client.generate("What is the DB migration plan?")

    call_args = mock_post.call_args
    payload = call_args.kwargs["json"]
    assert payload["messages"] == [{"role": "user", "content": "What is the DB migration plan?"}]
    assert payload["temperature"] == 0.3
    assert payload["enable_enhancement"] is False

    headers = call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer test-key"