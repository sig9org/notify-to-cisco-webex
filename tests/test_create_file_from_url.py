import httpx
import mimetypes

from notify_to_cisco_webex.notify_to_cisco_webex import Webex, WebexConfig


def test_create_file_from_url_uses_content_disposition_and_content_type():
    """If the response has Content-Disposition and Content-Type, use them."""
    cfg = WebexConfig(token="dummy_token", dst="room123", msg_format="markdown")
    client = Webex(cfg)

    content = b"\x89PNG\r\n\x1a\nPNG-DATA"
    headers = {
        "content-type": "image/png",
        "content-disposition": 'attachment; filename="from_cd.png"',
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content, headers=headers)

    transport = httpx.MockTransport(handler)
    # Replace the client's underlying httpx.Client with a mock transport client
    client._client = httpx.Client(transport=transport)

    f = client.create_file_from_url("https://example.com/download?id=123")

    assert f is not None
    assert f.blob == content
    assert f.filename == "from_cd.png"
    assert f.extension == "png"
    assert f.mime_type == "image/png"

    # close client
    try:
        client._client.close()
    except Exception:
        pass


def test_create_file_from_url_infers_filename_from_url_path_and_content_type_hdr():
    """If Content-Disposition is absent, filename should be taken from URL path and content-type used."""
    cfg = WebexConfig(token="dummy_token", dst="room123", msg_format="markdown")
    client = Webex(cfg)

    content = b"\xff\xd8\xffJPEG-DATA"
    headers = {
        "content-type": "image/jpeg",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content, headers=headers)

    transport = httpx.MockTransport(handler)
    client._client = httpx.Client(transport=transport)

    url = "https://example.com/path/to/fruits.jpg"
    f = client.create_file_from_url(url)

    assert f is not None
    assert f.blob == content
    assert f.filename == "fruits.jpg"
    assert f.extension == "jpg"
    # Expect Content-Type header to be used
    assert f.mime_type == "image/jpeg"
    # Also verify guessed mime (sanity)
    expected_mime, _ = mimetypes.guess_type(f.filename)
    assert expected_mime == "image/jpeg"

    # close client
    try:
        client._client.close()
    except Exception:
        pass
