import argparse
import csv
import io
import os
import re
import urllib.parse
import urllib.request
from typing import List, Dict, Tuple, Optional
from db import Database

OPENDATA_PAGE_URL = "https://www.mhlw.go.jp/stf/kaigo-kouhyou_opendata.html"

HEADER_MAP = {
    '都道府県コード又は市町村コード': 'code',
    'No': 'no',
    '都道府県名': 'pref_name',
    '市区町村名': 'city_name',
    '事業所名': 'facility_name',
    '事業所名カナ': 'facility_kana',
    'サービスの種類': 'service_type',
    '住所': 'address',
    '方書（ビル名等）': 'building',
    '緯度': 'lat',
    '経度': 'lng',
    '電話番号': 'tel',
    'FAX番号': 'fax',
    '法人番号': 'corporate_no',
    '法人の名称': 'corporate_name',
    '事業所番号': 'facility_no',
    '利用可能曜日': 'available_days',
    '利用可能曜日特記事項': 'available_days_note',
    '定員': 'capacity',
    'URL': 'url',
    '高齢者の方と障害者の方が同時一体的に利用できるサービス': 'shared_service',
    '介護保険の通常の指定基準を満たしている': 'kaigo_standard',
    '障害福祉の通常の指定基準を満たしている': 'shogai_standard',
    '備考': 'remarks'
}

def fetch_opendata_csv_links(page_url: str = OPENDATA_PAGE_URL) -> List[Tuple[str, str, str]]:
    """厚労省ページから (ファイル識別子/ラベル, ファイル名, 絶対URL) のリストを取得"""
    req = urllib.request.Request(page_url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode('utf-8', errors='ignore')

    matches = re.findall(r'<a[^>]+href=[\"\']([^\"\']+\.csv)[\"\'][^>]*>(.*?)</a>', html, re.DOTALL)
    results = []
    for href, text in matches:
        clean_text = re.sub(r'<[^>]+>', '', text).strip()
        # ［15.4MB］ などの容量表示を削除
        clean_text = re.sub(r'［.*?］', '', clean_text).strip()
        full_url = urllib.parse.urljoin(page_url, href)
        file_name = os.path.basename(href)
        identifier = clean_text if clean_text else file_name
        results.append((identifier, file_name, full_url))
    return results

def parse_csv_content(csv_bytes: bytes) -> List[Dict[str, str]]:
    """CSVデータのバイト列を解析して標準キーの辞書リストを返す"""
    text = csv_bytes.decode('utf-8-sig', errors='replace')
    reader = csv.DictReader(io.StringIO(text))
    
    records = []
    for row in reader:
        # キーの前後空白やBOM除去
        cleaned_row = {k.strip(): (v.strip() if v else "") for k, v in row.items() if k}
        mapped_record = {}
        for original_key, mapped_key in HEADER_MAP.items():
            mapped_record[mapped_key] = cleaned_row.get(original_key, "")
        records.append(mapped_record)
    return records

def import_csv_file(db: Database, identifier: str, file_name: str, url: str) -> int:
    """指定のCSVをダウンロードしDBに保存"""
    print(f"Downloading: {identifier} ({url})...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as resp:
        csv_bytes = resp.read()

    records = parse_csv_content(csv_bytes)
    print(f"Parsed {len(records)} records. Registering source file...")
    source_file_id = db.register_source_file(identifier, file_name, url)

    print("Inserting records into database...")
    inserted_count = db.insert_facilities(source_file_id, records)
    print(f"Successfully inserted {inserted_count} records for {identifier}.")
    return inserted_count

def run_import(file_filter: Optional[str] = None, db_path: str = "kaigo.db") -> int:
    db = Database(db_path)
    db.init_db()

    links = fetch_opendata_csv_links()
    if not links:
        print("No CSV links found on MHLW open data page.")
        return 0

    if file_filter:
        filtered_links = [
            link for link in links
            if file_filter in link[0] or file_filter in link[1]
        ]
        if not filtered_links:
            print(f"No CSV links matching filter '{file_filter}' found.")
            return 0
        links = filtered_links

    total_inserted = 0
    for identifier, file_name, url in links:
        try:
            inserted = import_csv_file(db, identifier, file_name, url)
            total_inserted += inserted
        except Exception as e:
            print(f"Error importing {identifier}: {e}")

    print(f"Total inserted records: {total_inserted}")
    return total_inserted

def main():
    parser = argparse.ArgumentParser(description="厚労省オープンデータから介護事業所CSVをインポートします")
    parser.add_argument("-f", "--file", help="取り込むファイル識別子またはファイル名（例: 110_訪問介護 や 110）")
    parser.add_argument("--db", default="kaigo.db", help="SQLiteデータベースファイルパス")
    args = parser.parse_args()

    run_import(file_filter=args.file, db_path=args.db)

if __name__ == "__main__":
    main()
