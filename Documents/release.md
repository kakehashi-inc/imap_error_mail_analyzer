# PyPI公開手順

## 概要

安全なリリースプロセスとして、以下の順序で実行します：
1. **TestPyPI**でのテスト公開
2. 動作確認
3. **本番PyPI**への公開

## 前提条件

### 1. アカウント設定

- **TestPyPI**: https://test.pypi.org/account/register/
- **PyPI**: https://pypi.org/account/register/

### 2. APIトークン取得

- **TestPyPI**: https://test.pypi.org/manage/account/token/
- **PyPI**: https://pypi.org/manage/account/token/

### 3. 認証設定

`.pypirc`ファイルをホームディレクトリに作成：

## Phase 1: TestPyPIでのテスト公開

### 1. パッケージのビルド

```bash
# 古いビルド成果物をクリーンアップ
rm -rf dist/ src/*.egg-info

# ビルドツールをインストール（初回のみ）
uv pip install build twine

# パッケージをビルド
uv run python -m build
```

### 2. ビルド結果の確認

```bash
# distディレクトリの内容を確認
ls dist/
# 以下のファイルが生成されているはずです：
# imap_error_mail_analyzer-x.x.x-py3-none-any.whl
# imap-error-mail-analyzer-x.x.x.tar.gz

# パッケージの内容を確認
tar -tf dist/imap-error-mail-analyzer-x.x.x.tar.gz | head -20
```

### 3. TestPyPIへのアップロード

```bash
# TestPyPIにアップロード
twine upload --repository testpypi dist/*

# または.pypirc使用時
python -m twine upload --repository testpypi dist/*
```

### 4. TestPyPIでの動作確認

```bash
# TestPyPIから直接テスト（推奨）
uvx --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ imap-error-mail-analyzer --help

# バージョン確認
uvx --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ imap-error-mail-analyzer --version

# 基本動作テスト
uvx --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ imap-error-mail-analyzer --transport stdio
```

**TestPyPIプロジェクトページ**: https://test.pypi.org/project/imap-error-mail-analyzer/

## Phase 2: 本番PyPIへの公開

### 1. TestPyPI動作確認完了後

TestPyPIでの全ての確認が完了したら、本番PyPIへアップロード：

```bash
# 本番PyPIにアップロード
twine upload dist/*

# または.pypirc使用時
python -m twine upload --repository pypi dist/*
```

### 2. 本番PyPIでの最終確認

```bash
# 本番PyPIから動作確認
uvx --force imap-error-mail-analyzer --help
uvx --force imap-error-mail-analyzer --version

# キャッシュクリア後のテスト
uv cache clean imap-error-mail-analyzer
uvx imap-error-mail-analyzer --help
```

**PyPIプロジェクトページ**: https://pypi.org/project/imap-error-mail-analyzer/

## **バージョンアップ時**

1. `pyproject.toml`のバージョンを更新（例: 0.1.0 → 0.1.1）
2. `CHANGELOG.md`を更新
3. gitでコミット＆タグ作成：
   ```bash
   git add -A
   git commit -m "Bump version to 0.1.1"
   git tag v0.1.1
   git push origin main --tags
   ```
4. 以降パッケージのビルド手順を参照
