import mimetypes
from pathlib import Path

from notify_to_cisco_webex.notify_to_cisco_webex import Webex, WebexConfig


def test_create_file_from_path_pdf():
    """create_file_from_path should read a local PDF and set metadata correctly."""
    cfg = WebexConfig(token="dummy_token", dst="room123", msg_format="markdown", timeout=5.0, insecure=False, verbose=False)
    client = Webex(cfg)

    path = Path("tests/assets/hello.pdf")
    assert path.exists(), "Test asset tests/assets/hello.pdf must exist"

    f = client.create_file_from_path(str(path))

    expected_mime, _ = mimetypes.guess_type(path.name)

    assert f.filename == "hello.pdf"
    assert isinstance(f.blob, (bytes, bytearray))
    assert len(f.blob) > 0
    assert f.extension == "pdf"
    assert f.mime_type == expected_mime

    # close httpx client to avoid resource warnings in test runs
    try:
        client._client.close()
    except Exception:
        pass


def test_create_file_from_path_image():
    """create_file_from_path should read a local image and set metadata correctly."""
    cfg = WebexConfig(token="dummy_token", dst="room123")
    client = Webex(cfg)

    path = Path("tests/assets/fruits.jpg")
    assert path.exists(), "Test asset tests/assets/fruits.jpg must exist"

    f = client.create_file_from_path(str(path))

    expected_mime, _ = mimetypes.guess_type(path.name)

    assert f.filename == "fruits.jpg"
    assert isinstance(f.blob, (bytes, bytearray))
    assert len(f.blob) > 0
    assert f.extension == "jpg"
    assert f.mime_type == expected_mime

    # close httpx client to avoid resource warnings in test runs
    try:
        client._client.close()
    except Exception:
        pass
