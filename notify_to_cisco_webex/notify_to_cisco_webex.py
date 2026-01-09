"""
notify_to_cisco_webex.notify_to_cisco_webex

This module provides a small client and CLI for sending messages and file
attachments to Cisco Webex.

Google-style docstrings are used throughout.

Notes:
- External dependencies: httpx, python-dotenv
- Designed for Python 3.10+
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import mimetypes
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

# Configure a module-level logger (prints to stderr)
logger = logging.getLogger("notify_to_cisco_webex")
handler = logging.StreamHandler(sys.stderr)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.propagate = False


@dataclass
class File:
    """Representation of a file attachment to be sent.

    Attributes:
        mime_type: MIME type of the file (e.g. "image/png"). Optional.
        filename: File name as sent to Webex.
        extension: File extension (without dot), optional.
        blob: Raw bytes of the file content.
    """

    mime_type: str | None = None
    filename: str | None = None
    extension: str | None = None
    blob: bytes | None = None


@dataclass
class WebexConfig:
    """Configuration for Webex client.

    Attributes:
        token: Webex access token (required).
        dst: Destination roomId or person email (required).
        msg_format: "text" or "markdown".
        timeout: HTTP timeout in seconds.
        insecure: If True, disables SSL verification.
        verbose: If True, enables verbose logging.
        proxy: Optional proxy URL to use for HTTP requests.
    """

    token: Optional[str] = None
    dst: Optional[str] = None
    msg_format: str = "markdown"
    timeout: float = 10.0
    insecure: bool = False
    verbose: bool = False
    proxy: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate basic configuration and normalize values."""
        if self.msg_format not in ("text", "markdown"):
            raise ValueError("msg_format must be 'text' or 'markdown'")


class Webex:
    """Client for sending messages and attachments to Cisco Webex.

    Usage:
        cfg = WebexConfig(token="...", dst="roomId", msg_format="markdown")
        client = Webex(cfg)
        result = client.send(message="hi", files=[...])

    Methods are instance methods (not static).
    """

    API_URL = "https://webexapis.com/v1/messages"

    def __init__(self, config: WebexConfig):
        """Initialize the client.

        Args:
            config: WebexConfig instance.

        Raises:
            ValueError: If token or dst are not provided.
        """
        self.config = config

        if not self.config.token:
            raise ValueError("WEBEX token is required")
        if not self.config.dst:
            raise ValueError("WEBEX dst is required")

        # Configure logging level
        if self.config.verbose:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)

        # Prepare httpx client options
        # Note: some httpx versions don't accept `proxies` in Client(...)
        # so construct the client without proxies and pass proxies per-request.
        self._client = httpx.Client(
            timeout=self.config.timeout,
            verify=not self.config.insecure,
        )

    # ----------------------------
    # Attachment helper methods
    # ----------------------------
    def create_file_from_path(self, path: Union[str, Path]) -> File:
        """Create a File object from a local filesystem path.

        Args:
            path: Local file path.

        Returns:
            File instance with content loaded into memory.

        Raises:
            FileNotFoundError: If the file does not exist.
            OSError: On read errors.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {path}")
        filename = p.name
        extension = p.suffix[1:] if p.suffix.startswith(".") else (p.suffix or None)
        mime_type, _ = mimetypes.guess_type(filename)
        blob = p.read_bytes()
        return File(mime_type=mime_type, filename=filename, extension=extension, blob=blob)

    def create_file_from_url(self, url: str) -> File:
        """Create a File object by fetching content from a URL.

        This method does not write to disk; it operates purely in memory.

        Args:
            url: HTTP or HTTPS URL pointing to the file.

        Returns:
            File instance.

        Raises:
            httpx.HTTPError: If the fetch fails.
            ValueError: If URL is invalid.
        """
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(f"Unsupported URL scheme for file: {url}")

        logger.debug("Fetching URL for attachment: %s", url)
        if self.config.proxy:
            resp = self._client.get(url, proxies=self.config.proxy)
        else:
            resp = self._client.get(url)
        resp.raise_for_status()
        content_disposition = resp.headers.get("content-disposition", "")
        # Try to infer filename from URL path or content-disposition
        filename = Path(parsed.path).name or None
        if "filename=" in content_disposition:
            # naive parsing
            parts = content_disposition.split("filename=")
            if len(parts) > 1:
                filename = parts[1].strip().strip('"').strip("'")
        extension = Path(filename).suffix[1:] if filename and Path(filename).suffix else None
        mime_type = resp.headers.get("content-type")
        blob = resp.content
        return File(mime_type=mime_type, filename=filename, extension=extension, blob=blob)

    def create_file_from_bytes(self, filename: str, blob: bytes, mime_type: Optional[str] = None) -> File:
        """Create a File object from raw bytes (module-only usage).

        If mime_type is omitted, the type is guessed from filename extension.

        Args:
            filename: Name of the file to present to Webex.
            blob: Raw bytes of the file.
            mime_type: Optional MIME type.

        Returns:
            File instance.
        """
        if mime_type is None:
            mime_type, _ = mimetypes.guess_type(filename)
        extension = Path(filename).suffix[1:] if Path(filename).suffix else None
        return File(mime_type=mime_type, filename=filename, extension=extension, blob=blob)

    # ----------------------------
    # Core send logic
    # ----------------------------
    def _build_target_fields(self) -> Dict[str, Any]:
        """Return fields for either roomId or toPersonEmail based on dst."""
        if "@" in self.config.dst:
            return {"toPersonEmail": self.config.dst}
        else:
            return {"roomId": self.config.dst}

    def _send_single(self, text: Optional[str], file_item: Optional[File]) -> Dict[str, Any]:
        """Send a single Webex message optionally with a single attachment.

        Args:
            text: Message body (text or markdown depending on config).
            file_item: Optional File to attach (or None).

        Returns:
            Parsed JSON response from Webex.

        Raises:
            httpx.HTTPStatusError: For non-2xx responses.
            RuntimeError: For other unexpected conditions.
        """
        fields = self._build_target_fields()
        if text:
            if self.config.msg_format == "markdown":
                fields["markdown"] = text
            else:
                fields["text"] = text

        headers = {"Authorization": f"Bearer {self.config.token}"}

        files_payload = None
        if file_item is not None:
            if not file_item.blob:
                raise RuntimeError("File has no content")
            # httpx expects a mapping like {"files": (filename, fileobj, content_type)}
            # Provide a BytesIO file-like object as the second element.
            file_obj = io.BytesIO(file_item.blob)
            file_tuple = (file_item.filename or "file", file_obj, file_item.mime_type or "application/octet-stream")
            files_payload = {"files": file_tuple}

        logger.debug("Sending Webex message to %s", self.config.dst)
        logger.debug("Payload fields: %s", fields)
        try:
            if files_payload:
                if self.config.proxy:
                    resp = self._client.post(self.API_URL, headers=headers, data=fields, files=files_payload, proxies=self.config.proxy)
                else:
                    resp = self._client.post(self.API_URL, headers=headers, data=fields, files=files_payload)
            else:
                if self.config.proxy:
                    resp = self._client.post(self.API_URL, headers=headers, json=fields, proxies=self.config.proxy)
                else:
                    resp = self._client.post(self.API_URL, headers=headers, json=fields)
            # Raise for bad HTTP status
            resp.raise_for_status()
            logger.debug("Webex response status: %s", resp.status_code)
            try:
                return resp.json()
            except Exception:
                # Return raw text if json parse fails
                return {"status_code": resp.status_code, "text": resp.text}
        except httpx.HTTPStatusError as exc:
            # Bubble up with useful context
            status = exc.response.status_code
            body = exc.response.text
            logger.debug("Webex HTTP error: %d %s", status, body)
            raise RuntimeError(f"Webex API returned {status}: {body}") from exc
        except httpx.HTTPError as exc:
            logger.debug("HTTP error when sending to Webex: %s", exc)
            raise RuntimeError(f"HTTP error when sending to Webex: {exc}") from exc

    def send(self, message: Optional[str] = None, files: Optional[List[Union[str, File]]] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Send a message and optional attachments to Webex.

        Behavior:
            - If neither message nor files is provided, raises ValueError.
            - If no files: send single message with text only.
            - If one file: send single message with text + file.
            - If multiple files: send first message with text + first file,
              then send subsequent messages with each remaining file and no text.

        Args:
            message: Message body. Optional when files are provided.
            files: List of attachments. Each item can be:
                - Local path string (will be read)
                - URL string (http/https) (will be fetched)
                - File instance (already prepared)

        Returns:
            JSON-decoded response dict (single request) or a list of dicts (multiple requests).

        Raises:
            ValueError: If both message and files are missing.
            RuntimeError: For HTTP/API related errors.
        """
        files = files or []
        prepared: List[File] = []

        # Normalize attachments
        for item in files:
            if isinstance(item, File):
                prepared.append(item)
            elif isinstance(item, (str, Path)):
                s = str(item)
                if s.startswith("http://") or s.startswith("https://"):
                    prepared.append(self.create_file_from_url(s))
                else:
                    prepared.append(self.create_file_from_path(s))
            else:
                raise ValueError("Unsupported file item type; must be path/url or File instance")

        if not message and not prepared:
            raise ValueError("Either message or files must be provided")

        results: List[Dict[str, Any]] = []
        try:
            if not prepared:
                # Single text-only message
                res = self._send_single(message, None)
                return res
            elif len(prepared) == 1:
                res = self._send_single(message, prepared[0])
                return res
            else:
                # Multiple attachments
                # First request: message + first file
                res = self._send_single(message, prepared[0])
                results.append(res)
                # Remaining files: no message
                for f in prepared[1:]:
                    res = self._send_single(None, f)
                    results.append(res)
                return results
        finally:
            # close client to release resources
            try:
                self._client.close()
            except Exception:
                pass


# ----------------------------
# CLI Entrypoint
# ----------------------------
def _load_env_files() -> None:
    """Load .env file without overwriting existing OS environment variables.

    This ensures precedence: CLI args > OS env > .env file.
    """
    load_dotenv(override=False)


def _parse_cli(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Namespace with parsed arguments.
    """
    parser = argparse.ArgumentParser(prog="notify-to-cisco-webex", description="Send messages and files to Cisco Webex")
    parser.add_argument("-t", "--token", help="Webex access token")
    parser.add_argument("-d", "--dst", help="Destination roomId or person email")
    parser.add_argument("-f", "--format", dest="msg_format", choices=["text", "markdown"], default=None, help="Message format (text or markdown)")
    parser.add_argument("--timeout", type=float, default=None, help="HTTP timeout seconds")
    parser.add_argument("--insecure", action="store_true", default=None, help="Disable SSL verification")
    parser.add_argument("-v", "--verbose", action="store_true", default=None, help="Enable verbose logging")
    parser.add_argument("-p", "--proxy", default=None, help="HTTP proxy URL")
    parser.add_argument("-m", "--message", default=None, help="Message body")
    parser.add_argument("--file", action="append", default=[], help="Attachment files/URLs (can be specified multiple times)")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """CLI main function.

    This function adheres to the exit code policy:
        0: success
        2: configuration error (missing required params)
        3: Webex API error
        4: unexpected error

    Args:
        argv: List of command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code integer.
    """
    _load_env_files()
    args = _parse_cli(argv)

    # Build effective configuration with precedence: CLI > OS env > .env
    token = args.token or os.environ.get("WEBEX_TOKEN")
    dst = args.dst or os.environ.get("WEBEX_DST")
    msg_format = args.msg_format or os.environ.get("WEBEX_FORMAT", "Markdown")
    timeout = args.timeout if args.timeout is not None else float(os.environ.get("WEBEX_TIMEOUT", "10"))
    insecure_env = os.environ.get("WEBEX_INSECURE")
    # CLI flag takes precedence if set (args.insecure may be True/False/None)
    if args.insecure is not None:
        insecure = bool(args.insecure)
    elif insecure_env is not None:
        insecure = insecure_env.lower() in ("1", "true", "yes", "on")
    else:
        insecure = False

    # verbose flag
    if args.verbose is not None:
        verbose = bool(args.verbose)
    else:
        verbose_env = os.environ.get("WEBEX_VERBOSE")
        verbose = bool(verbose_env and verbose_env.lower() in ("1", "true", "yes", "on"))

    proxy = args.proxy or os.environ.get("WEBEX_PROXY")

    # Normalize msg_format to lowercase (accept Markdown default)
    msg_format = msg_format.lower() if isinstance(msg_format, str) else "markdown"

    cfg = WebexConfig(
        token=token,
        dst=dst,
        msg_format=msg_format,
        timeout=timeout,
        insecure=insecure,
        verbose=verbose,
        proxy=proxy,
    )

    # Set logger level per verbose
    if cfg.verbose:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.WARNING)

    # Validate presence of at least message or file(s)
    message = args.message
    files = args.file or []

    if not message and not files:
        # Missing both - error code 2
        logger.error("Either message or at least one file must be specified.")
        return 2

    # Create client and send
    try:
        client = Webex(cfg)
        # For CLI, files are provided as paths or URLs (strings)
        result = client.send(message=message, files=files)
        # On success, CLI must print nothing and exit 0
        return 0
    except ValueError as exc:
        # Configuration error (missing token/dst etc)
        logger.error("Configuration error: %s", exc)
        return 2
    except RuntimeError as exc:
        # Webex API errors or http errors are surfaced as RuntimeError
        logger.error("Webex API error: %s", exc)
        return 3
    except Exception as exc:  # pragma: no cover - unexpected
        logger.exception("Unexpected error: %s", exc)
        return 4


# If executed as module, expose main entry
if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
