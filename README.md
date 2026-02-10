# IMAP Error Mail Analyzer

複数のIMAPアカウントからバウンスメール(5xxエラー)を検出し、Ollamaで対応すべき担当者を分類してJSONレポートを生成するツール。

## 機能

- 複数IMAPアカウントの一括チェック
- 5xxバウンスメールの自動検出(DSN / 本文テキスト解析)
- OllamaによるAI分類(IPブロック / ドメインブロック / レート制限 / サーバーエラー / 設定エラー / 宛先不明 / 容量超過)
- ユーザー起因エラー(宛先不明、メールボックス容量超過)を自動除外
- 日付+アカウント名付きJSONレポート出力(対象/対象外の2ファイル)
- 処理済みメールのハッシュキャッシュによる重複処理スキップ

## インストール

### PyPIからのクイックインストール

PyPIに公開後、簡単にインストール・実行できます：

```bash
# uv使用（推奨）
uvx imap-error-mail-analyzer  # インストールせずに直接実行

# またはグローバルインストール
uv tool install imap-error-mail-analyzer

# またはpipでインストール
pip install imap-error-mail-analyzer
```

### ソースからのインストール

#### 前提条件

仮想環境を作成・有効化：

```bash
python -m venv venv

# Windows
.\venv\Scripts\Activate.ps1

# Linux/macOS
source venv/bin/activate
```

### 基本インストール

プロジェクトを編集可能モードでインストール：

#### プロダクション使用

```bash
pip install -e "."
```

#### 開発

開発ツールを含めてインストール：

```bash
pip install -e ".[dev]"
```

### 依存関係

**実行依存関係**:

- `requests` - Ollama API通信

**開発依存関係**（`[dev]`でインストール）:

- `pylint` - コードリント
- `pylint-plugin-utils` - Pylintユーティリティ
- `black` - コードフォーマット

### インストール例

#### クイックスタート（プロダクション）

```bash
# クローンしてプロダクション用インストール
git clone <repository-url>
cd imap-error-mail-analyzer
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
pip install -e "."
```

#### 開発者セットアップ

```bash
# クローンして開発環境セットアップ
git clone <repository-url>
cd imap-error-mail-analyzer
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
pip install -e ".[dev]"

# 開発ツール実行
black src/
pylint src/
```

## セットアップ

### 1. 設定ファイル作成

`config.example.json` をコピーして `config.json` を作成：

```bash
cp config.example.json config.json
```

### 2. 設定項目

| キー | 説明 | デフォルト |
|------|------|-----------|
| `default_days` | 取得日数 | `7` |
| `log_dir` | ログ出力ディレクトリ | `"logs"` |
| `ollama.base_url` | Ollama APIのURL | `"http://localhost:11434"` |
| `ollama.model` | 使用するモデル名 | `"gemma3:4b"` |
| `accounts.<name>.host` | IMAPサーバーホスト | (必須) |
| `accounts.<name>.port` | IMAPサーバーポート | (必須) |
| `accounts.<name>.username` | ログインユーザー名 | (必須) |
| `accounts.<name>.password` | ログインパスワード | (必須) |
| `accounts.<name>.security` | 接続方式 (`ssl` / `starttls` / `none`) | `"ssl"` |
| `accounts.<name>.check` | チェック対象フォルダ | `["INBOX"]` |

### 3. Ollamaの準備

ローカルまたはリモートでOllamaを起動し、使用するモデルをプルしておく：

```bash
ollama pull gemma3:12b
```

## 使用方法

### コマンドラインオプション

```bash
imap-error-mail-analyzer --help
```

### コマンド例

```bash
# バージョン確認
imap-error-mail-analyzer --version

# デフォルト設定で実行(config.jsonのdefault_days日間)
imap-error-mail-analyzer

# 日数指定(config.jsonのdefault_daysを上書き)
imap-error-mail-analyzer --days 30

# カスタム設定ファイル使用
imap-error-mail-analyzer --config /path/to/config.json

# 詳細出力
imap-error-mail-analyzer -v
```

### uvでの使用

```bash
# 直接実行
uvx imap-error-mail-analyzer
```

### Pythonでの使用

```bash
# activate後にpythonで実行
python -m imap_error_mail_analyzer.main
```

## 出力

### JSONファイル

`log_dir` に以下の2ファイルが出力されます：

- `{YYYYMMDD}_{アカウント名}_target.json` - 対応が必要なエラー(IPブロック/ドメインブロック/レート制限/サーバーエラー/設定エラー)
- `{YYYYMMDD}_{アカウント名}_excluded.json` - ユーザー起因のエラー(宛先不明/容量超過)

### JSONフィールド

| フィールド | 説明 |
|--------|------|
| `date` | バウンスメールの日付 |
| `folder` | メールフォルダ |
| `error_code` | 5xxエラーコード |
| `error_cause` | エラーの原因(5xxの原因) |
| `ai_responsible_party` | AIによる対応すべき人 |
| `ai_reason` | AIの判定理由 |
| `from_addr` | 元の送信者アドレス |
| `to_addr` | 配信失敗した宛先アドレス |
| `subject` | 元メールの件名 |
| `body_plain` | text/plain本文(先頭1000文字、空白・改行正規化済み) |
| `body_html` | text/html本文(body抽出、style/script除去、HTMLタグ保持、先頭1000文字) |

### 処理済みキャッシュ

`{log_dir}/cache/{アカウント名}_processed.json` に処理済みメールのハッシュが保存されます。
取得日数を過ぎた古いエントリは自動的に削除されます。

## 開発者向けリファレンス

### 開発ルール

- 開発者の参照するドキュメントは`README.md`を除き`Documents`に配置すること。
- importは循環インポートが発生しない限りトップレベルで行うこと。
- pylintで警告や注意が表示されないように考慮しながら開発を行うこと。
- 対応後は必ず`pylint src/`で確認を行い適切な修正を行うこと。故意にリンターエラーを許容する際は、ユーザーに確認をし許可があれば、除外理由をコメントで明記すること。
- Pythonの処理を記載する中で部品化するものは`src/imap_error_mail_analyzer/utils/`にファイルを作成して実装すること。
- 一時的なスクリプトなど（例:調査用スクリプト）は`scripts`ディレクトリに配置すること。
- システムの動作などに変更があった場合は、`Documents/システム仕様.md`を更新すること。
