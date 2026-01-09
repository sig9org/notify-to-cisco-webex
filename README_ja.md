# notify-to-cisco-webex

このリポジトリは、Cisco Webex にメッセージ（および添付ファイル）を送信するための小さな Python ツール／ライブラリです。CLI ツールとしても Python モジュールとしても利用できます。

## 概要

- Webex の `roomId` またはメールアドレス宛にメッセージを送信できます。
- 添付ファイルを送信可能（Webex の仕様では 1 メッセージに添付できるファイルは 1 つのため、複数ファイルは分割送信します）。
- メッセージ形式は `text` または `markdown` を指定可能です。
- 日本語などのマルチバイト文字に対応しています。
- 設定の優先順位は CLI 引数 > OS 環境変数 > `.env` ファイル です。

## インストール

必要な外部ライブラリは以下の 2 つのみです（このプロジェクトの方針に従っています）:

- `httpx`
- `python-dotenv`

例（仮想環境を使う推奨）:

```/dev/null/install.sh#L1-5
python -m venv .venv
. .venv/bin/activate
pip install httpx python-dotenv
```

パッケージをプロジェクト内で開発利用する場合は、ソースのルートで:

```/dev/null/install-editable.sh#L1-3
pip install -e .
```

## 環境変数 / パラメータ

以下の設定は CLI 引数、環境変数、`.env` ファイルの順で解決されます（CLI が最優先）。

| 環境変数名       | CLI オプション    | 説明                                               |
| ---------------- | ----------------- | -------------------------------------------------- |
| `WEBEX_TOKEN`    | `--token`, `-t`   | Webex アクセストークン（必須）                     |
| `WEBEX_DST`      | `--dst`, `-d`     | 宛先の `roomId` またはメールアドレス（必須）       |
| `WEBEX_FORMAT`   | `--format`, `-f`  | `text` または `markdown`（デフォルト: `markdown`） |
| `WEBEX_TIMEOUT`  | `--timeout`       | HTTP タイムアウト（秒、デフォルト: `10`）          |
| `WEBEX_INSECURE` | `--insecure`      | SSL 証明書検証を無効化するフラグ                   |
| `WEBEX_VERBOSE`  | `--verbose`, `-v` | 詳細ログを出力するフラグ                           |
| `WEBEX_PROXY`    | `--proxy`, `-p`   | HTTP プロキシの URL                                |

補足:

- CLI の `--message` / `-m`（メッセージ本文）および `--file`（添付ファイル、複数回指定可能）は、どちらも任意ですが、両方指定されない場合はエラーになります。
- `WEBEX_DST` に `@` が含まれる場合は `toPersonEmail`（メール送信）、含まれない場合は `roomId`（ルーム送信）として扱います。

## 使い方

### Python モジュールとして使う

ライブラリの中心は `WebexConfig` と `Webex` クラスです。`Webex` の `send` メソッドはインスタンスメソッドとして実装されています。

例:

```/dev/null/usage.py#L1-16
from notify_to_cisco_webex.notify_to_cisco_webex import WebexConfig, Webex

cfg = WebexConfig(token="YOUR_TOKEN", dst="roomId_or_person@example.com")
client = Webex(cfg)
# message: 文字列、files: ローカルファイルパスのリスト（任意）
result = client.send(message="Hello from module", files=["/path/to/1.png", "/path/to/2.pdf"])
print(result)  # dict（単一リクエスト）または list（複数リクエスト）
```

- プログラムから呼び出した場合、送信が成功すると JSON（パース済みの dict または dict の list）を返します。
- `Webex` インスタンス生成後に `msg_format` や `proxy` などのプロパティを変更することで動作を変更できます。

### CLI として使う

以下のようにモジュールを実行します（`WEBEX_TOKEN` と `WEBEX_DST` は環境変数や `.env`、あるいは CLI で指定してください）:

```/dev/null/cli_example.sh#L1-6
# 環境変数で指定済みの場合
python -m notify_to_cisco_webex -m "Hello from CLI"
# 添付ファイルを複数指定
python -m notify_to_cisco_webex -m "Files attached" --file /path/to/1.png --file /path/to/2.pdf
```

- CLI 実行時の挙動:
    - 正常終了時: 標準出力には何も表示しません（exit code 0）。
    - エラー時: stderr にエラーメッセージを出力し、非ゼロの終了コードを返します。
    - `--verbose` を指定すると、エラー時や成功時に API レスポンスなどの詳細が stderr に出力されます。

## 添付ファイルの挙動

- Webex の仕様により 1 メッセージに添付できるファイルは 1 つです。本ツールは次のように振る舞います:
    - 添付ファイルがない場合: 本文のみを 1 回のリクエストで送信します。
    - 添付ファイルが 1 つの場合: 本文と添付を 1 回のリクエストで送信します。
    - 添付ファイルが複数の場合: 本文と最初の添付ファイルを 1 回目のリクエストで送信し、残りの添付ファイルは本文なしで順次別リクエストとして送信します。

画像（JPEG/PNG 等）を添付した場合、受信側の Webex クライアントでは画像として表示されます。

## テスト

テストフレームワークには `pytest` を利用します。ネットワークアクセスはテストの中でモックされており、実際の Webex API にはアクセスしません。

テストの実行方法:

```/dev/null/test_run.sh#L1-4
pip install pytest
pytest -q
```

- テストファイル:
    - `tests/test_notify.py` — 添付ファイルのないメッセージ送信のテスト
    - `tests/test_attachments.py` — 添付ファイルのあるメッセージ送信のテスト

## ライセンス

このプロジェクトは MIT ライセンスの下で配布されています。詳細は `LICENSE` ファイルを参照してください。

---
