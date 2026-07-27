import argparse
import sys
import asyncio

import import_data
import scrape_emails
import export_csv
import status
import backup

def main():
    parser = argparse.ArgumentParser(
        description="介護企業メールアドレス収集・データ管理ツール CLI"
    )
    subparsers = parser.add_subparsers(dest="command", help="実行するコマンドを選択してください")

    # 1. import コマンド
    p_import = subparsers.add_parser("import", help="厚労省オープンデータCSVをインポート")
    p_import.add_argument("-f", "--file", help="取り込むファイル識別子またはファイル名（例: 110_訪問介護 や 110）")
    p_import.add_argument("--db", default="kaigo.db", help="SQLiteデータベースファイルパス")

    # 2. scrape コマンド
    p_scrape = subparsers.add_parser("scrape", help="事業所Webサイトからメールアドレスを自動収集")
    p_scrape.add_argument("-f", "--file", help="取り込みファイル識別子またはファイル名（例: 110_訪問介護）")
    p_scrape.add_argument("--code", help="都道府県コード又は市町村コード")
    p_scrape.add_argument("--pref", help="都道府県名（例: 北海道）")
    p_scrape.add_argument("--city", help="市区町村名（例: 札幌市中央区）")
    p_scrape.add_argument("-n", "--limit", type=int, help="処理件数上限")
    p_scrape.add_argument("--interval", type=float, default=1.0, help="ページ遷移ごとの待機秒数（デフォルト: 1.0秒）")
    p_scrape.add_argument("-b", "--batch-size", type=int, default=50, help="ブラウザ再起動を行う件数単位（デフォルト: 50件）")
    p_scrape.add_argument("--facility-timeout", type=float, default=45.0, help="1事業所あたりの全体最大タイムアウト秒数（デフォルト: 45秒）")
    p_scrape.add_argument("--db", default="kaigo.db", help="SQLiteデータベースファイルパス")
    p_scrape.add_argument("--head", action="store_true", help="ブラウザ画面を表示して実行")

    # 3. export コマンド
    p_export = subparsers.add_parser("export", help="データとメールアドレスをCSVに出力")
    p_export.add_argument("-f", "--file", help="取り込みファイル識別子またはファイル名（例: 110_訪問介護）")
    p_export.add_argument("--code", help="都道府県コード又は市町村コード")
    p_export.add_argument("--pref", help="都道府県名")
    p_export.add_argument("--city", help="市区町村名")
    p_export.add_argument("-o", "--output", default="kaigo_facilities_with_emails.csv", help="出力先CSVファイルパス")
    p_export.add_argument("--db", default="kaigo.db", help="SQLiteデータベースファイルパス")

    # 4. status コマンド
    p_status = subparsers.add_parser("status", help="データ登録およびメール収集の進捗状況を表示")
    p_status.add_argument("-f", "--file", help="取り込みファイル識別子またはファイル名（例: 110_訪問介護）")
    p_status.add_argument("--code", help="都道府県コード又は市町村コード")
    p_status.add_argument("--pref", help="都道府県名")
    p_status.add_argument("--city", help="市区町村名")
    p_status.add_argument("--db", default="kaigo.db", help="SQLiteデータベースファイルパス")

    # 5. backup コマンド
    p_backup = subparsers.add_parser("backup", help="データベースのバックアップを作成")
    p_backup.add_argument("--db", default="kaigo.db", help="SQLiteデータベースファイルパス")
    p_backup.add_argument("--dir", default="backup", help="バックアップ保存先フォルダ")

    # 6. restore コマンド
    p_restore = subparsers.add_parser("restore", help="バックアップファイルからデータベースを復元")
    p_restore.add_argument("-f", "--file", required=True, help="復元元バックアップファイル名")
    p_restore.add_argument("--db", default="kaigo.db", help="復元先SQLiteデータベースファイルパス")
    p_restore.add_argument("--dir", default="backup", help="バックアップ保存先フォルダ")

    args = parser.parse_args()

    if args.command == "import":
        import_data.run_import(file_filter=args.file, db_path=args.db)
    elif args.command == "scrape":
        asyncio.run(scrape_emails.run_scraper(
            file_filter=args.file,
            code=args.code,
            pref=args.pref,
            city=args.city,
            limit=args.limit,
            interval=args.interval,
            batch_size=args.batch_size,
            facility_timeout=args.facility_timeout,
            db_path=args.db,
            headless=not args.head
        ))
    elif args.command == "export":
        export_csv.export_facilities_to_csv(
            db_path=args.db,
            output_file=args.output,
            file_filter=args.file,
            code=args.code,
            pref=args.pref,
            city=args.city
        )
    elif args.command == "status":
        status.display_status(
            db_path=args.db,
            file_filter=args.file,
            code=args.code,
            pref=args.pref,
            city=args.city
        )
    elif args.command == "backup":
        backup.create_backup(db_path=args.db, backup_dir=args.dir)
        backup.list_backups(backup_dir=args.dir)
    elif args.command == "restore":
        backup.restore_backup(file_identifier=args.file, db_path=args.db, backup_dir=args.dir)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
