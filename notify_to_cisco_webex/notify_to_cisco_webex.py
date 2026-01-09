"""
notify_to_cisco_webex.notify_to_cisco_webex

Module that implements a small client to send messages (with optional attachments)
to Cisco Webex and a CLI entry point.

This module uses `httpx` for HTTP requests and `python-dotenv` for loading
defaults from a `.env` file.

Google-style docstrings are used throughout.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import httpx
from dotenv import dotenv_values

# Constants
WEBEX_API_MESSAGES = "https://webexapis.com/v1/messages"
DEFAULT_FORMAT = "markdown"
DEFAULT_TIMEOUT = 10.0


class WebexError(Exception):
    """Generic exception for Webex client errors."""


@dataclass
class WebexConfig:
    """Configuration holder for Webex client.

    Attributes:
        token: Webex access token.
        dst: Destination roomId or person email.
        msg_format: Either 'text' or 'markdown'.
        timeout: HTTP request timeout in seconds.
        insecure: If True, disable TLS cert verification.
        verbose: If True, print verbose logs.
        proxy: Optional HTTP proxy URL.
    """

    token: str
    dst: str
    msg_format: str = DEFAULT_FORMAT
    timeout: float = DEFAULT_TIMEOUT
    insecure: bool = False
    verbose: bool = False
    proxy: Optional[str] = None


class Webex:
    """Client for sending messages to Cisco Webex.

    The primary message sending method is `send`. It is an instance method
    (not static) and other connection parameters can be modified on the
    instance after creation.

    Example:
        config = WebexConfig(token="...", dst="roomid")
        client = Webex(config)
        client.msg_format = "text"
        client.send("hello", files=["/path/to/a.png"])
    """

    def __init__(self, config: WebexConfig) -> None:
        """Initialize Webex client.

        Args:
            config: A `WebexConfig` instance containing connection settings.
        """
        self.config = config
        # Use a client per instance to allow persistent settings like proxies.
        self._client: Optional[httpx.Client] = None

    def _ensure_client(self) -> httpx.Client:
        """Create and return an httpx.Client configured from `self.config`.

        Returns:
            An instance of `httpx.Client`.
        """
        if self._client is None:
            client_kwargs: Dict[str, Any] = {}
            # Timeout
            client_kwargs["timeout"] = httpx.Timeout(self.config.timeout)
            # SSL verification
            client_kwargs["verify"] = not self.config.insecure
            # Proxy
            if self.config.proxy:
                # httpx accepts proxies either as a single URL or mapping; use directly.
                client_kwargs["proxies"] = self.config.proxy
            self._client = httpx.Client(**client_kwargs)
        return self._client

    @staticmethod
    def _is_email(dst: str) -> bool:
        """Return True if the destination looks like an email address.

        Args:
            dst: Destination string.

        Returns:
            True if `dst` contains '@' and looks like an email.
        """
        return "@" in dst and " " not in dst

    @staticmethod
    def _guess_mimetype(path: str) -> str:
        """Guess a mimetype for a file path.

        Args:
            path: Path to the file.

        Returns:
            Guessed mimetype or 'application/octet-stream' if unknown.
        """
        mtype, _ = mimetypes.guess_type(path)
        return mtype or "application/octet-stream"

    def _prepare_destination_field(self) -> Tuple[str, Tuple[str, str]]:
        """Prepare the destination field name and value.

        Returns:
            A tuple of (field_name, (field_name, value)) suitable for building
            request data. The outer tuple is (field_name, (field_name, value))
            to simplify usage with form data.
        """
        if self._is_email(self.config.dst):
            return "toPersonEmail", ("toPersonEmail", self.config.dst)
        return "roomId", ("roomId", self.config.dst)

    def _build_headers(self) -> Dict[str, str]:
        """Build headers for Webex API requests.

        Returns:
            Headers dictionary including Authorization.
        """
        return {"Authorization": f"Bearer {self.config.token}"}

    def send(self, message: Optional[str] = None, files: Optional[Sequence[str]] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Send a message and optional attachments to Webex.

        The method accepts the message body and a list of local file paths.
        At least one of `message` or `files` must be provided.

        For attachment sending:
            - If no files are provided: send a single message with text/markdown only.
            - If one file is provided: send message + that file in one request.
            - If multiple files are provided: send first file together with message
              (if any). Send remaining files in additional requests without message.

        Args:
            message: Message body (text or markdown depending on `config.msg_format`).
            files: Sequence of local file paths to attach.

        Returns:
            If a single request is made, returns the parsed JSON response as a dict.
            If multiple requests are made, returns a list of parsed JSON responses.

        Raises:
            WebexError: On invalid arguments, I/O errors reading files, HTTP errors.
        """
        if not message and not files:
            raise WebexError("Either 'message' or 'files' must be provided.")

        files_list = list(files) if files else []
        dest_field_name, dest_pair = self._prepare_destination_field()
        headers = self._build_headers()
        client = self._ensure_client()

        results: List[Dict[str, Any]] = []

        # Helper to send a single multipart request with optional message and one file
        def _send_single(body_message: Optional[str], file_path: Optional[str]) -> Dict[str, Any]:
            form_fields: Dict[str, Union[str, bytes]] = {}
            # destination
            form_fields[dest_field_name] = self.config.dst
            # message body: choose field name based on format
            if body_message:
                if self.config.msg_format.lower() == "text":
                    form_fields["text"] = body_message
                else:
                    # default to markdown
                    form_fields["markdown"] = body_message

            files_payload = None
            if file_path:
                if not os.path.isfile(file_path):
                    raise WebexError(f"Attachment not found: {file_path}")
                try:
                    fp = open(file_path, "rb")
                except OSError as e:
                    raise WebexError(f"Failed to open attachment '{file_path}': {e}") from e
                filename = os.path.basename(file_path)
                content_type = self._guess_mimetype(file_path)
                # httpx expects files param similar to requests: list/tuple of (name, (filename, fileobj, content_type))
                files_payload = [("files", (filename, fp, content_type))]
            try:
                if self.config.verbose:
                    print(f"[DEBUG] POST {WEBEX_API_MESSAGES} dest={self.config.dst} file={file_path} message_len={len(body_message) if body_message else 0}", file=sys.stderr)

                if file_path:
                    # multipart/form-data request when attaching a file
                    resp = client.post(
                        WEBEX_API_MESSAGES,
                        headers=headers,
                        data=form_fields,
                        files=files_payload,
                    )
                else:
                    # For message-only requests, use JSON body to ensure UTF-8 is preserved
                    json_payload = form_fields
                    # Merge headers but ensure content-type indicates UTF-8 JSON
                    json_headers = {**headers, "Content-Type": "application/json; charset=utf-8"}
                    resp = client.post(
                        WEBEX_API_MESSAGES,
                        headers=json_headers,
                        json=json_payload,
                    )
            finally:
                if files_payload:
                    # close file objects
                    for _, tup in files_payload:
                        fobj = tup[1]
                        try:
                            fobj.close()
                        except Exception:
                            pass

            if resp.status_code >= 400:
                # Try to include response body where available
                detail = ""
                try:
                    detail = resp.text
                except Exception:
                    pass
                raise WebexError(f"Webex API error {resp.status_code}: {detail}")
            try:
                return resp.json()
            except Exception as e:
                raise WebexError(f"Failed to parse Webex API response as JSON: {e}")

        # If no files, single request with just message
        if not files_list:
            result = _send_single(message, None)
            return result

        # If files present
        # First file: include message (if any)
        first = files_list[0]
        results.append(_send_single(message, first))
        # Remaining files: send without message
        for path in files_list[1:]:
            results.append(_send_single(None, path))

        # If only one request was made, return single dict for convenience
        if len(results) == 1:
            return results[0]
        return results


def _parse_bool(value: Optional[str], default: bool = False) -> bool:
    """Parse a boolean-like value from environment or CLI.

    Accepts typical truthy strings ('1', 'true', 'yes', 'on') case-insensitively.

    Args:
        value: Input string or None.
        default: Default boolean if value is None or empty.

    Returns:
        Parsed boolean.
    """
    if value is None:
        return default
    val = str(value).strip().lower()
    if val in ("1", "true", "yes", "on"):
        return True
    if val in ("0", "false", "no", "off"):
        return False
    return default


def _build_config_from_sources(cli_args: argparse.Namespace) -> WebexConfig:
    """Build a WebexConfig using the priority: CLI args > OS env vars > .env file.

    Args:
        cli_args: Parsed arguments from argparse.

    Returns:
        WebexConfig instance.

    Raises:
        WebexError: If required settings (token or dst) are missing after resolving.
    """
    # Load .env values (lowest priority)
    env_dotenv = dotenv_values() or {}  # type: ignore[assignment]

    # Now get OS environment (higher priority than .env)
    env_os = dict(os.environ)

    # Helper to resolve by priority
    def resolve(key: str, cli_val: Optional[Any], default: Optional[str] = None) -> Optional[str]:
        # CLI has highest priority: for flags we look at cli_val explicitly
        if isinstance(cli_val, str) and cli_val != "":
            return cli_val
        if cli_val is not None and isinstance(cli_val, bool):
            # for boolean flags represented as booleans on CLI, let caller handle
            return str(cli_val)
        # Then OS env
        if key in env_os and env_os[key] != "":
            return env_os[key]
        # Then .env
        if key in env_dotenv and env_dotenv[key] is not None and env_dotenv[key] != "":
            return env_dotenv[key]
        return default

    token = resolve("WEBEX_TOKEN", cli_args.token)
    dst = resolve("WEBEX_DST", cli_args.dst)
    msg_format = resolve("WEBEX_FORMAT", cli_args.format, DEFAULT_FORMAT) or DEFAULT_FORMAT
    timeout_raw = resolve("WEBEX_TIMEOUT", None)
    if cli_args.timeout is not None:
        timeout_raw = str(cli_args.timeout)
    timeout = float(timeout_raw) if timeout_raw is not None and str(timeout_raw) != "" else DEFAULT_TIMEOUT

    insecure_raw = resolve("WEBEX_INSECURE", None)
    if cli_args.insecure:
        insecure_raw = "1"
    insecure = _parse_bool(insecure_raw, False)

    verbose_raw = resolve("WEBEX_VERBOSE", None)
    if cli_args.verbose:
        verbose_raw = "1"
    verbose = _parse_bool(verbose_raw, False)

    proxy = resolve("WEBEX_PROXY", cli_args.proxy) or None

    if not token:
        raise WebexError("WEBEX_TOKEN must be specified via CLI or environment or .env")
    if not dst:
        raise WebexError("WEBEX_DST must be specified via CLI or environment or .env")

    cfg = WebexConfig(
        token=token,
        dst=dst,
        msg_format=msg_format,
        timeout=timeout,
        insecure=insecure,
        verbose=verbose,
        proxy=proxy,
    )
    return cfg


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entrypoint for the notify tool.

    This function parses command-line arguments, constructs a `Webex` client,
    sends the message/attachments, and exits. On successful completion nothing
    is printed. On error a message is printed to stderr and a non-zero exit
    code is returned.

    Args:
        argv: List of command-line arguments (excluding program name). If None,
            `sys.argv[1:]` will be used.

    Returns:
        Exit code (0 for success, non-zero for failures).
    """
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(prog="notify_to_cisco_webex", description="Send message (and optional attachments) to Cisco Webex.")
    parser.add_argument("-t", "--token", help="Webex access token (overrides environment WEBEX_TOKEN)")
    parser.add_argument("-d", "--dst", help="Destination roomId or person email (overrides WEBEX_DST)")
    parser.add_argument("-f", "--format", choices=["text", "markdown"], default=None, help="Message format: 'text' or 'markdown' (overrides WEBEX_FORMAT)")
    parser.add_argument("--timeout", type=float, default=None, help="HTTP timeout in seconds (overrides WEBEX_TIMEOUT)")
    parser.add_argument("--insecure", action="store_true", help="Disable SSL certificate verification (overrides WEBEX_INSECURE)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output (overrides WEBEX_VERBOSE)")
    parser.add_argument("-p", "--proxy", help="HTTP proxy URL (overrides WEBEX_PROXY)")
    parser.add_argument("-m", "--message", help="Message body to send (optional)")
    parser.add_argument("--file", dest="files", action="append", help="Local file path to attach. May be specified multiple times.")

    args = parser.parse_args(list(argv))

    try:
        config = _build_config_from_sources(args)
    except WebexError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 2

    client = Webex(config)

    # Send and handle results according to CLI rules:
    # - If successful: print nothing and exit 0
    # - If failure: print error and exit non-zero
    try:
        # Note: CLI passes message and files from args. The module API returns JSON on success.
        res = client.send(message=args.message, files=args.files)
        # CLI: on success print nothing
        if config.verbose:
            # For debugging, print JSON to stderr if verbose
            print(json.dumps(res, ensure_ascii=False, indent=2), file=sys.stderr)
        return 0
    except WebexError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 3
    except Exception as e:  # pragma: no cover - safety net
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
