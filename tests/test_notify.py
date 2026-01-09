"""
Tests for sending messages without attachments.

Updated to expect JSON payloads for message-only requests so UTF-8
/ multibyte characters are preserved.
"""

from __future__ import annotations

import json

import httpx
import pytest

from notify_to_cisco_webex import Webex, WebexConfig, WEBEX_API_MESSAGES


def _make_client_factory(handler):
    """
    Return a factory function that creates an httpx.Client using a MockTransport
    with the provided handler. This is used to monkeypatch httpx.Client so the
    production code will use the mock transport.
    """
    real_client = httpx.Client

    def factory(*args, **kwargs):
        transport = httpx.MockTransport(handler)
        return real_client(*args, transport=transport, **kwargs)

    return factory


def test_send_message_markdown(monkeypatch):
    """Send a markdown message (multibyte text) without attachments using JSON body."""
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        # Validate URL
        assert str(request.url) == WEBEX_API_MESSAGES
        # Validate Authorization header is present and correct
        auth = request.headers.get("authorization", "")
        assert auth == "Bearer test-token"
        # Content-Type should indicate JSON with UTF-8
        ct = request.headers.get("content-type", "")
        assert "application/json" in ct.lower()
        # Read and parse JSON body
        body_bytes = request.read()
        body_text = body_bytes.decode("utf-8")
        payload = json.loads(body_text)
        # Destination field should be roomId in this test
        assert payload.get("roomId") == "room-id-12345"
        # The message contains multibyte characters
        assert payload.get("markdown") == "こんにちは (markdown)"
        seen["ok"] = True
        return httpx.Response(200, json={"id": "msg-1"})

    # Monkeypatch httpx.Client to inject our MockTransport
    monkeypatch.setattr(httpx, "Client", _make_client_factory(handler))

    cfg = WebexConfig(
        token="test-token",
        dst="room-id-12345",
        msg_format="markdown",
        timeout=5.0,
        insecure=False,
        verbose=False,
        proxy=None,
    )
    client = Webex(cfg)
    result = client.send(message="こんにちは (markdown)")

    assert isinstance(result, dict)
    assert result.get("id") == "msg-1"
    assert seen.get("ok", False) is True


def test_send_message_text_field(monkeypatch):
    """Send a text message (plain text format) without attachments using JSON body."""
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == WEBEX_API_MESSAGES
        auth = request.headers.get("authorization", "")
        assert auth == "Bearer token-xyz"
        ct = request.headers.get("content-type", "")
        assert "application/json" in ct.lower()
        body_bytes = request.read()
        body_text = body_bytes.decode("utf-8")
        payload = json.loads(body_text)
        # When format is 'text' the payload should include the 'text' field.
        assert payload.get("toPersonEmail") == "user@example.com"
        assert payload.get("text") == "Hello plain text"
        seen["ok"] = True
        return httpx.Response(200, json={"id": "msg-plain"})

    monkeypatch.setattr(httpx, "Client", _make_client_factory(handler))

    cfg = WebexConfig(
        token="token-xyz",
        dst="user@example.com",  # exercise email destination path
        msg_format="text",
        timeout=3.0,
        insecure=True,
        verbose=False,
        proxy=None,
    )
    client = Webex(cfg)
    result = client.send(message="Hello plain text")

    assert isinstance(result, dict)
    assert result["id"] == "msg-plain"
    assert seen.get("ok", False) is True
