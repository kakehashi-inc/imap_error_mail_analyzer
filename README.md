# IMAP Error Mail Analyzer

複数のIMAPアカウントからバウンスメール(5xxエラー)を検出し、Ollamaで対応すべき担当者を分類してJSONレポートを生成するツール。

## 機能

- 複数IMAPアカウントの一括チェック
- 5xxバウンスメールの自動検出(DSN / 本文テキスト解析)
- OllamaによるAI分類(IPブロック / ドメインブロック / 送信スロットリング / サーバーエラー / 設定エラー / 宛先不明 / 容量超過 / 受信者レート制限)
- ユーザー起因エラー(宛先不明、メールボックス容量超過、受信者レート制限)を自動除外
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
| `report_dir` | HTMLレポート出力ディレクトリ | `"reports"` |
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

### サブコマンド

```bash
imap-error-mail-analyzer --help
```

| サブコマンド | 説明 |
| --- | --- |
| `run` | バウンスメール取得・分類・レポート生成 |
| `cleanup` | 指定日のレポートJSONとキャッシュエントリを削除 |
| `report` | 指定日のレポートを表示 |
| `version` | バージョン表示(`-v` と同じ) |

### コマンド例

```bash
# バージョン確認
imap-error-mail-analyzer -v

# デフォルト設定で実行(config.jsonのdefault_days日間)
imap-error-mail-analyzer run

# 日数指定(config.jsonのdefault_daysを上書き)
imap-error-mail-analyzer run --days 30

# カスタム設定ファイル使用
imap-error-mail-analyzer -c /path/to/config.json run

# 詳細出力
imap-error-mail-analyzer -V run

# 指定日のレポートとキャッシュを削除(日付省略時は今日)
imap-error-mail-analyzer cleanup 2026-02-10
imap-error-mail-analyzer cleanup

# レポート表示(日付省略時は今日)
imap-error-mail-analyzer report
imap-error-mail-analyzer report 2026-02-10

# カテゴリを指定してレポート表示
imap-error-mail-analyzer report --category ip_block,config_error

# アカウントを指定してレポート表示
imap-error-mail-analyzer report --accounts account1,account2

# ボディ内容を含めて詳細表示
imap-error-mail-analyzer report --detail
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

- `{YYYYMMDD}_{アカウント名}_target.json` - 対応が必要なエラー(IPブロック/ドメインブロック/送信スロットリング/サーバーエラー/設定エラー)
- `{YYYYMMDD}_{アカウント名}_excluded.json` - ユーザー起因のエラー(宛先不明/容量超過/受信者レート制限)

### JSONフィールド

| フィールド | 説明 |
|--------|------|
| `date` | バウンスメールの日付 |
| `folder` | メールフォルダ |
| `error_code` | 5xxエラーコード |
| `error_message` | エラーメッセージ |
| `ai_responsible_party` | AIによる対応すべき人 |
| `ai_reason` | AIの判定理由 |
| `from_addr` | 元の送信者アドレス |
| `to_addr` | 配信失敗した宛先アドレス |
| `subject` | 元メールの件名 |
| `body_plain` | バウンス通知のtext/plain(エラー内容のみ、先頭1000文字) |
| `body_html` | バウンス通知のtext/html(エラー内容のみ、先頭1000文字) |
| `body_plain_original` | 元メッセージのtext/plain(先頭1000文字) |
| `body_html_original` | 元メッセージのtext/html(先頭1000文字) |
| `delivery_status` | DSNの構造化フィールド(dict) |

### HTMLレポート

`run` コマンド完了時に `report_dir` (デフォルト: `reports`) に `report_{YYYYMMDD}.html` が自動生成されます。

- Bootstrap 5によるレスポンシブデザイン
- 全アカウントを1ファイルに統合、アカウント別 > target/excluded のセクション構造
- テーブルカラム: Date(日付/時間改行), Detail(Category+Reason+Error Code+Message統合), From, To, Subject, Body(ボタン)
- Bodyボタンクリックでモーダルダイアログに本文を表示

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
