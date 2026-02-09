# Gmail Attachment Downloader

概要を記載

## 機能

- 機能を記載

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
ruff check src/
```

## セットアップ

### 1. 設定ファイル作成

`config.json`ファイルを作成（`config.example.json`を参考）

## 使用方法

### コマンドラインオプション

```bash
imap-error-mail-analyzer --help
```

### コマンド例

```bash
# バージョン確認
imap-error-mail-analyzer --version
```

### 基本使用法

```bash
# 過去7日間の添付ファイルをダウンロード（デフォルト）
imap-error-mail-analyzer

# 日数指定
imap-error-mail-analyzer --days 30

# カスタム設定ファイル使用
imap-error-mail-analyzer --config /path/to/config.json

# 詳細出力
imap-error-mail-analyzer -v
```

### uvでの使用

```bash
# 直接実行
uvx imap-error-mail-analyzer --days 7
```

## 開発者向けリファレンス

### 開発ルール

- 開発者の参照するドキュメントは`README.md`を除き`Documents`に配置すること。
- 対応後は必ずリンターで確認を行い適切な修正を行うこと。故意にリンターエラーを許容する際は、その旨をコメントで明記すること。 **ビルドはリリース時に行うものでデバックには不要なのでリンターまでで十分**
- 一時的なスクリプトなど（例:調査用スクリプト）は`scripts`ディレクトリに配置すること。
