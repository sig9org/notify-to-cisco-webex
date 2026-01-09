import mimetypes

from notify_to_cisco_webex.notify_to_cisco_webex import Webex, WebexConfig


def test_create_file_from_bytes_with_mime():
    """Ensure create_file_from_bytes preserves provided MIME type and content."""
    cfg = WebexConfig(token="dummy_token", dst="room123", msg_format="markdown", timeout=5.0, insecure=False, verbose=False)
    client = Webex(cfg)

    blob = b"hello world"
    filename = "hello.txt"
    mime = "text/plain"

    f = client.create_file_from_bytes(filename, blob, mime_type=mime)

    assert f.filename == filename
    assert f.blob == blob
    assert f.mime_type == mime
    assert f.extension == "txt"

    # Close underlying httpx client to avoid resource warnings
    try:
        client._client.close()
    except Exception:
        pass


def test_create_file_from_bytes_guesses_mime():
    """When MIME type is omitted, it should be guessed from the filename."""
    cfg = WebexConfig(token="dummy_token", dst="room123", msg_format="markdown")
    client = Webex(cfg)

    blob = b"\x89PNG\r\n\x1a\n"
    filename = "image.png"

    # Ensure system knows about .png mapping
    expected_mime, _ = mimetypes.guess_type(filename)

    f = client.create_file_from_bytes(filename, blob)

    assert f.filename == filename
    assert f.blob == blob
    assert f.extension == "png"
    assert f.mime_type == expected_mime

    # Close underlying httpx client to avoid resource warnings
    try:
        client._client.close()
    except Exception:
        pass
