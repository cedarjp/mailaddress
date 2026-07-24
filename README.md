# 介護企業メールアドレス収集・データ管理システム

厚生労働省の「介護サービス情報公表システム」オープンデータ（CSV）を取り込み、SQLiteデータベースに保管した上で、Playwrightを用いて各事業所Webサイトからメールアドレスを自動収集し、最終的に統合CSVとして出力するツールです。

MacおよびWindows11環境のどちらでも同様に動作します。

---

## 🛠️ 事前準備・セットアップ

### 1. Python環境および依存ライブラリのインストール

```bash
# 仮想環境を作成して有効化
python -m venv .venv

# Mac / Linux の場合:
source .venv/bin/activate

# Windows の場合 (PowerShell):
# .venv\Scripts\Activate.ps1

# 依存ライブラリのインストール
pip install -r requirements.txt

# Playwright ブラウザ (Chromium) のインストール
playwright install chromium
```

---

## 🚀 使い方（3つのコマンド）

単一エントリーポイント `python main.py <command>` または個別スクリプトから実行できます。

### 1. データ取り込みコマンド (`import`)

厚労省の公表データ（CSV）を自動ダウンロードし、SQLiteデータベース (`kaigo.db`) に登録します。

```bash
# 全データを取り込む場合
python main.py import

# 特定のサービス（例: 「110_訪問介護」）のみ取り込む場合
python main.py import -f 110_訪問介護

# または個別スクリプト実行
python import_data.py -f 110
```

### 2. メールアドレス収集コマンド (`scrape`)

登録済みの事業所Webサイトにアクセスし、Playwrightでメールアドレスを自動探索・保存します。

- ページ遷移ごとにデフォルトで **1秒のウェイト** を差し挟みます。
- メールアドレスが見つかった時点で該当事業所の探索を終了します。
- 1件ごとにDB保存・ステータス更新を行うため、途中で終了・中断しても次回起動時に取得済みの事業所は自動でスキップされます。

```bash
# 基本実行 (全件対象)
python main.py scrape

# オプション指定の例:
# - 「110_訪問介護」のデータで、北海道札幌市中央区の事業所を最大10件スクレイピング
python main.py scrape -f 110_訪問介護 --pref 北海道 --city 札幌市中央区 -n 10

# 都道府県コード指定 + 間隔2秒
python main.py scrape --code 011011 --interval 2.0 -n 50

# または個別スクリプト実行
python scrape_emails.py -f 110 --limit 10
```

#### スライド・スクレイピング指定オプション

| オプション | 説明 |
| :--- | :--- |
| `-f`, `--file` | 取り込みファイル識別子またはファイル名（例: `110_訪問介護` や `110`） |
| `--code` | 都道府県コード又は市町村コード |
| `--pref` | 都道府県名（例: `北海道`, `東京都`） |
| `--city` | 市区町村名（例: `札幌市中央区`, `千代田区`） |
| `-n`, `--limit` | 処理件数の上限指定 |
| `--interval` | ページ遷移ごとの待機秒数（デフォルト: `1.0`秒） |
| `--db` | 使用するSQLiteファイルパス（デフォルト: `kaigo.db`） |
| `--head` | ブラウザ画面を表示して実行（デバッグ用） |

---

### 3. CSVエクスポートコマンド (`export`)

DB内の事業所情報に取得したメールアドレスを結合し、ExcelやWindowsでも文字化けしないBOM付きUTF-8 (`utf-8-sig`) 形式でCSV出力します。

```bash
# 全データをCSV出力
python main.py export -o output.csv

# 条件絞り込み（「110_訪問介護」かつ「東京都」のデータのみ出力）
python main.py export -f 110_訪問介護 --pref 東京都 -o tokyo_110.csv

# または個別スクリプト実行
python export_csv.py -f 110 -o result.csv
```

---

### 4. 状況確認コマンド (`status`)

DBのデータ登録件数、スクレイピング進捗率、獲得メールアドレス総数、サービス別・都道府県別の獲得内訳を表示します。

```bash
# 全体の進捗・収集状況を表示
python main.py status

# 「110_訪問介護」かつ「東京都」だけに絞った進捗状況を表示
python main.py status -f 110_訪問介護 --pref 東京都

# または個別スクリプト実行
python status.py -f 110
```

---

## 🧪 テストの実行

全テストスイート（DB、インポート、スクレイピング解析、エクスポート、ステータス、CLI統合テスト）を実行します。

```bash
pytest
```

