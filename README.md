# notify-to-cisco-webex

English / 日本語

---

## English

### Overview

`notify-to-cisco-webex` is a small Python tool and library to send messages (including attachments) to Cisco Webex. It supports sending plain text or Markdown messages, attaching local files (images, PDFs, etc.), and can be used both as a CLI tool and as a Python module.

Key behaviours:

- Supports multibyte characters (e.g. Japanese) in message bodies.
- Attachment rules:
    - No attachments: send a single message with the body.
    - One attachment: send the body and attachment in a single request.
    - Multiple attachments: send the body with the first attachment in the first request, then send each remaining attachment in separate requests (Webex restricts one file per message).
- Configuration precedence: CLI arguments > OS environment variables > `.env` file.

### Installation

Install dependencies (the project uses only the allowed external libraries):

- `httpx`
- `python-dotenv`

For development, create a virtual environment and install dependencies from `pyproject.toml` or manually:

    python -m venv .venv
    . .venv/bin/activate
    pip install httpx python-dotenv
    # or install the package in editable mode if using the project source:
    pip install -e .

### Environment variables / Parameters

The tool accepts configuration via CLI flags, OS environment variables, or a `.env` file (in that order of precedence).

| Environment variable | CLI option        | Description                                                |
| -------------------- | ----------------- | ---------------------------------------------------------- |
| `WEBEX_TOKEN`        | `--token`, `-t`   | Webex access token (required)                              |
| `WEBEX_DST`          | `--dst`, `-d`     | Destination roomId or person email (required)              |
| `WEBEX_FORMAT`       | `--format`, `-f`  | Message format: `text` or `markdown` (default: `markdown`) |
| `WEBEX_TIMEOUT`      | `--timeout`       | HTTP request timeout in seconds (default: 10)              |
| `WEBEX_INSECURE`     | `--insecure`      | Disable SSL verification (flag)                            |
| `WEBEX_VERBOSE`      | `--verbose`, `-v` | Enable verbose logging (flag)                              |
| `WEBEX_PROXY`        | `--proxy`, `-p`   | HTTP proxy URL                                             |

Notes:

- The CLI also accepts `--message` / `-m` (message body) and one or more `--file` entries (attachment file paths). At least one of `--message` or `--file` must be provided.
- If destination contains `@` it is treated as a person email (`toPersonEmail`); otherwise it is treated as a `roomId`.

### Usage

Python module usage

- Typical usage from your Python code:

    from notify_to_cisco_webex.notify_to_cisco_webex import Webex, WebexConfig

    cfg = WebexConfig(
    token="YOUR_WEBEX_TOKEN",
    dst="roomId_or_person@example.com",
    msg_format="markdown",
    timeout=10.0,
    insecure=False,
    verbose=False,
    proxy=None,
    )

    client = Webex(cfg)
    result = client.send(message="Hello from module", files=["/path/to/1.png", "/path/to/2.pdf"])

    # result is a dict (single request) or list of dicts (multiple requests)

CLI usage

- Examples (the CLI prints nothing on success):
    - Send a message (using environment variables or explicit flags):

        python -m notify_to_cisco_webex -m "Hello from CLI"

    - Send message with one or more files:

        python -m notify_to_cisco_webex -m "Files attached" --file /path/to/1.png --file /path/to/2.pdf

    - Set token and dst via CLI flags:

        python -m notify_to_cisco_webex -t "TOKEN" -d "roomId" -m "Hi"

Verbose mode

- Add `-v` / `--verbose` to print debugging output and API responses to stderr.

Exit codes (CLI)

- `0` : success (no output)
- `2` : configuration error (e.g. missing token or dst)
- `3` : Webex API error
- `4` : unexpected error

### Tests

- Tests are implemented using `pytest`.
- Test files live under the project's `tests/` directory:
    - `tests/test_notify.py` — sending messages without attachments
    - `tests/test_attachments.py` — sending messages with attachments
- Tests use an HTTP mocking approach (via `httpx.MockTransport`) so they don't make real network calls.

### License

This project is licensed under the MIT License. See the `LICENSE` file for details.

---

## 日本語

### 概要

`notify-to-cisco-webex` は、Cisco Webex にメッセージ（添付ファイル含む）を送信するための小さな Python ツール／ライブラリです。プレーンテキストや Markdown のメッセージ送信、ローカルファイルの添付（画像や PDF など）に対応し、CLI と Python モジュールの両方として利用できます。

主な挙動:

- 日本語などのマルチバイト文字をメッセージに利用可能。
- 添付ファイルの取り扱い:
    - 添付なし: 本文のみを1回のリクエストで送信。
    - 添付1つ: 本文とファイルを1回のリクエストで送信。
    - 添付複数: 最初のリクエストに本文と1つ目のファイルを含め、残りは本文なしで順次別リクエストで送信（Webex の仕様で 1 メッセージに添付できるファイルは 1 つのため）。
- 設定の優先順位: コマンドライン > OS 環境変数 > `.env` ファイル。

### インストール

必要な外部ライブラリ:

- `httpx`
- `python-dotenv`

開発環境の例:

    python -m venv .venv
    . .venv/bin/activate
    pip install httpx python-dotenv
    # 開発中にソースからインストールする場合:
    pip install -e .

### 環境変数 / パラメータ

CLI 引数、OS 環境変数、.env ファイルで設定可能（優先順位は CLI > 環境変数 > .env）。

| 環境変数         | CLI オプション    | 説明                                                               |
| ---------------- | ----------------- | ------------------------------------------------------------------ |
| `WEBEX_TOKEN`    | `--token`, `-t`   | Webex アクセストークン（必須）                                     |
| `WEBEX_DST`      | `--dst`, `-d`     | 送信先の roomId またはメールアドレス（必須）                       |
| `WEBEX_FORMAT`   | `--format`, `-f`  | メッセージ形式: `text` または `markdown`（デフォルト: `markdown`） |
| `WEBEX_TIMEOUT`  | `--timeout`       | HTTP タイムアウト（秒、デフォルト: 10）                            |
| `WEBEX_INSECURE` | `--insecure`      | SSL 検証を無効化（フラグ）                                         |
| `WEBEX_VERBOSE`  | `--verbose`, `-v` | 詳細ログ有効（フラグ）                                             |
| `WEBEX_PROXY`    | `--proxy`, `-p`   | HTTP プロキシ URL                                                  |

補足:

- CLI では `--message`/`-m`（本文）と `--file`（添付ファイル、複数指定可能）を受け付けます。`--message` と `--file` の両方が未指定の場合はエラーになります。
- `WEBEX_DST` に `@` が含まれる場合はメールアドレス（`toPersonEmail`）として扱い、含まれない場合は `roomId` として扱います。

### 使い方

Python モジュールとして

- 例:

    from notify_to_cisco_webex.notify_to_cisco_webex import Webex, WebexConfig

    cfg = WebexConfig(
    token="YOUR_WEBEX_TOKEN",
    dst="roomId_or_person@example.com",
    msg_format="markdown",
    timeout=10.0,
    insecure=False,
    verbose=False,
    proxy=None,
    )

    client = Webex(cfg)
    result = client.send(message="モジュールからの送信", files=["/path/to/1.png", "/path/to/2.pdf"])

    # result は dict（単一リクエスト）または dict のリスト（複数リクエスト）

CLI から

- 例（成功時は標準出力に何も表示されません）:
    - メッセージ送信:

        python -m notify_to_cisco_webex -m "CLI からの送信"

    - 添付ファイル付き送信:

        python -m notify_to_cisco_webex -m "ファイル添付" --file /path/to/1.png --file /path/to/2.pdf

- トークンや送信先を CLI で指定する例:

    python -m notify_to_cisco_webex -t "TOKEN" -d "roomId" -m "こんにちは"

詳細ログ

- `-v` / `--verbose` を付けるとデバッグログや API レスポンスが stderr に表示されます。

終了コード（CLI）

- `0` : 成功（出力なし）
- `2` : 設定エラー（例: token や dst が未指定）
- `3` : Webex API エラー
- `4` : 想定外のエラー

### テスト

- `pytest` を用いてテストを実行できます。
- テストは `tests/` ディレクトリに配置されています:
    - `tests/test_notify.py` — 添付ファイルなしの送信テスト
    - `tests/test_attachments.py` — 添付ファイルありの送信テスト
- テストは `httpx.MockTransport` を使ってネットワークアクセスをモックしています。

### ライセンス

本プロジェクトは MIT ライセンスの下で配布されます。詳細は `LICENSE` ファイルを参照してください。
