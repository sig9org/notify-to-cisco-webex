"""
Tests for sending messages with attachments.

The tests use httpx.MockTransport to intercept requests and validate that
the multipart form bodies include the expected filenames, file contents,
destination fields, and message fields according to the specification:

- Single attachment: message + file in one request.
- Multiple attachments: first request contains message + first file, remaining
  attachments are sent in subsequent requests without the message.
"""
from __future__ import annotations

import os
from typing import List

import httpx
import pytest

from notify_to_cisco_webex import Webex, WebexConfig, WEBEX_API_MESSAGES


def _make_client_factory(handler):
    """
    Return a factory which constructs an httpx.Client using MockTransport
    backed by the provided handler.
    """
    # Capture the real httpx.Client constructor before we monkeypatch it so
    # that the factory can call the original implementation and avoid recursion.
    real_client = httpx.Client

    def factory(*args, **kwargs):
        transport = httpx.MockTransport(handler)
        # Create a real client but inject the mock transport so the code under
        # test performs requests against our handler.
        return real_client(*args, transport=transport, **kwargs)

    return factory


def _path_in_tests(fname: str) -> str:
    """Return an absolute path to a file placed in the tests directory."""
    return os.path.join(os.path.dirname(__file__), fname)


def test_single_attachment(monkeypatch, tmp_path):
    """When sending a single attachment, the request contains the message and the file."""
    # Create a temporary attachment file in the provided tmp_path so tests do not
    # depend on repository working directory or external files.
    p = tmp_path / "1.pdf"
    p.write_bytes(b"sample content\n")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        # Validate target URL and headers
        assert str(request.url) == WEBEX_API_MESSAGES
        auth = request.headers.get("authorization", "")
        assert auth == "Bearer attach-token"

        body = request.read()
        # Destination field must be present
        assert b"roomId" in body
        # The filename of the attached file should appear in the multipart body
        assert b'filename="1.pdf"' in body

        # Validate that actual file bytes are present in the body
        file_path = str(p)
        with open(file_path, "rb") as fh:
            sample = fh.read(64)
        assert sample in body

        # Message should be present in the same request (markdown by default)
        assert b"markdown" in body
        assert "attachment single".encode() in body

        seen["ok"] = True
        return httpx.Response(200, json={"id": "msg-single"})

    monkeypatch.setattr(httpx, "Client", _make_client_factory(handler))

    cfg = WebexConfig(
        token="attach-token",
        dst="room-123",
        msg_format="markdown",
        timeout=5.0,
        insecure=False,
        verbose=False,
        proxy=None,
    )
    client = Webex(cfg)
    result = client.send(message="attachment single", files=[str(p)])

    assert isinstance(result, dict)
    assert result.get("id") == "msg-single"
    assert seen.get("ok", False)


def test_multiple_attachments(monkeypatch, tmp_path):
    """When sending multiple attachments, first request includes message + first file,
    subsequent requests include remaining files only.
    """
    # Create temporary files in tmp_path with the expected filenames and contents.
    p1 = tmp_path / "2.jpg"
    p2 = tmp_path / "3.png"
    p1.write_bytes(b"JPEGDATA")
    p2.write_bytes(b"PDFDATA")

    calls: List[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        idx = len(calls)
        body = request.read()
        calls.append(body)

        # Common validations
        assert str(request.url) == WEBEX_API_MESSAGES
        auth = request.headers.get("authorization", "")
        assert auth == "Bearer multi-token"
        # Destination must be present in every request
        assert b"roomId" in body

        if idx == 0:
            # First request: should contain the first file and the message (markdown)
            assert b'filename="2.jpg"' in body
            assert b"markdown" in body
            assert "hello multiple".encode() in body
        elif idx == 1:
            # Second request: should contain the second file only and no message field
            assert b'filename="3.png"' in body
            assert b"markdown" not in body and b"text" not in body
        else:
            pytest.fail("Unexpected additional request")

        return httpx.Response(200, json={"id": f"msg-{idx}"})

    monkeypatch.setattr(httpx, "Client", _make_client_factory(handler))

    cfg = WebexConfig(
        token="multi-token",
        dst="room-456",
        msg_format="markdown",
        timeout=5.0,
        insecure=False,
        verbose=False,
        proxy=None,
    )
    client = Webex(cfg)

    files = [str(p1), str(p2)]
    result = client.send(message="hello multiple", files=files)

    # When multiple requests are made the client returns a list of results
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0].get("id") == "msg-0"
    assert result[1].get("id") == "msg-1"
    # Ensure handler saw both requests
    assert len(calls) == 2
