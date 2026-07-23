import tempfile
import os
import unittest
from unittest.mock import patch, MagicMock
from db import Database
from import_data import parse_csv_content, fetch_opendata_csv_links, run_import

SAMPLE_HTML = """
<html>
<body>
  <a href="/content/12300000/jigyosho_110.csv">110_訪問介護［15.4MB］</a>
  <a href="/content/12300000/jigyosho_120.csv">120_訪問入浴介護［673KB］</a>
</body>
</html>
"""

SAMPLE_CSV = """都道府県コード又は市町村コード,No,都道府県名,市区町村名,事業所名,事業所名カナ,サービスの種類,住所,方書（ビル名等）,緯度,経度,電話番号,FAX番号,法人番号,法人の名称,事業所番号,利用可能曜日,利用可能曜日特記事項,定員,URL,高齢者の方と障害者の方が同時一体的に利用できるサービス,介護保険の通常の指定基準を満たしている,障害福祉の通常の指定基準を満たしている,備考
011011,001,北海道,札幌市中央区,テスト介護所,テストカイゴショ,訪問介護,札幌市中央区1-1,,43.0,141.0,011-000-0000,,1234567890123,テスト法人,0170101950,,,,http://example-test.com,,,,
"""

class TestImportData(unittest.TestCase):
    def test_parse_csv_content(self):
        records = parse_csv_content(SAMPLE_CSV.encode('utf-8-sig'))
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec["code"], "011011")
        self.assertEqual(rec["facility_name"], "テスト介護所")
        self.assertEqual(rec["url"], "http://example-test.com")

    @patch('urllib.request.urlopen')
    def test_fetch_opendata_csv_links(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = SAMPLE_HTML.encode('utf-8')
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        links = fetch_opendata_csv_links("https://www.mhlw.go.jp/test.html")
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0][0], "110_訪問介護")
        self.assertEqual(links[0][1], "jigyosho_110.csv")

    @patch('urllib.request.urlopen')
    def test_run_import(self, mock_urlopen):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # 1回目はHTML取得、2回目はCSV取得
            mock_html_resp = MagicMock()
            mock_html_resp.read.return_value = SAMPLE_HTML.encode('utf-8')
            mock_html_resp.__enter__.return_value = mock_html_resp

            mock_csv_resp = MagicMock()
            mock_csv_resp.read.return_value = SAMPLE_CSV.encode('utf-8-sig')
            mock_csv_resp.__enter__.return_value = mock_csv_resp

            mock_urlopen.side_effect = [mock_html_resp, mock_csv_resp]

            inserted = run_import(file_filter="110", db_path=db_path)
            self.assertEqual(inserted, 1)

            db = Database(db_path)
            facilities = db.get_facilities_to_scrape()
            self.assertEqual(len(facilities), 1)
            self.assertEqual(facilities[0]["facility_name"], "テスト介護所")

        finally:
            if os.path.exists(db_path):
                os.remove(db_path)

if __name__ == '__main__':
    unittest.main()
