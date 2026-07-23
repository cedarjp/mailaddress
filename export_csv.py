import argparse
import csv
from typing import Optional
from db import Database

CSV_HEADER = [
    '都道府県コード又は市町村コード', 'No', '都道府県名', '市区町村名', '事業所名',
    '事業所名カナ', 'サービスの種類', '住所', '方書（ビル名等）', '緯度', '経度',
    '電話番号', 'FAX番号', '法人番号', '法人の名称', '事業所番号', '利用可能曜日',
    '利用可能曜日特記事項', '定員', 'URL',
    '高齢者の方と障害者の方が同時一体的に利用できるサービス',
    '介護保険の通常の指定基準を満たしている',
    '障害福祉の通常の指定基準を満たしている', '備考',
    '取り込みファイル識別子', '取り込みファイル名',
    'メールアドレス', 'メール取得元URL'
]

def export_facilities_to_csv(
    db_path: str = "kaigo.db",
    output_file: str = "kaigo_facilities_with_emails.csv",
    file_filter: Optional[str] = None,
    code: Optional[str] = None,
    pref: Optional[str] = None,
    city: Optional[str] = None
) -> int:
    db = Database(db_path)
    db.init_db()

    records = db.export_combined_data(
        file_identifier=file_filter,
        code=code,
        pref_name=pref,
        city_name=city
    )

    print(f"Exporting {len(records)} records to '{output_file}'...")

    with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)

        for rec in records:
            row = [rec[col] if rec[col] is not None else "" for col in CSV_HEADER]
            writer.writerow(row)

    print(f"Successfully exported to '{output_file}'.")
    return len(records)

def main():
    parser = argparse.ArgumentParser(description="登録済みの介護事業所データと取得したメールアドレスをCSVに出力します")
    parser.add_argument("-f", "--file", help="取り込みファイル識別子またはファイル名（例: 110_訪問介護）")
    parser.add_argument("--code", help="都道府県コード又は市町村コード")
    parser.add_argument("--pref", help="都道府県名")
    parser.add_argument("--city", help="市区町村名")
    parser.add_argument("-o", "--output", default="kaigo_facilities_with_emails.csv", help="出力先CSVファイルパス")
    parser.add_argument("--db", default="kaigo.db", help="SQLiteデータベースファイルパス")

    args = parser.parse_args()

    export_facilities_to_csv(
        db_path=args.db,
        output_file=args.output,
        file_filter=args.file,
        code=args.code,
        pref=args.pref,
        city=args.city
    )

if __name__ == "__main__":
    main()
