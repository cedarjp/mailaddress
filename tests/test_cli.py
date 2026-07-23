import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import main
from db import Database

SAMPLE_HTML = """
<html><body>
<a href="/content/12300000/jigyosho_120.csv">120_訪問入浴介護</a>
</body></html>
"""

SAMPLE_CSV = """都道府県コード又は市町村コード,No,都道府県名,市区町村名,事業所名,事業所名カナ,サービスの種類,住所,方書（ビル名等）,緯度,経度,電話番号,FAX番号,法人番号,法人の名称,事業所番号,利用可能曜日,利用可能曜日特記事項,定員,URL,高齢者の方と障害者の方が同時一体的に利用できるサービス,介護保険の通常の指定基準を満たしている,障害福祉の通常の指定基準を満たしている,備考
011011,001,北海道,札幌市中央区,訪問入浴テスト,テスト,訪問入浴介護,札幌市中央区1-1,,43.0,141.0,011-000-0000,,1234567890123,テスト法人,0170101950,,,,http://example.com,,,,
"""

class TestCLI(unittest.TestCase):
    @patch('urllib.request.urlopen')
    def test_cli_import_and_export(self, mock_urlopen):
        db_fd, db_path = tempfile.mkstemp(suffix=".db")
        out_fd, out_path = tempfile.mkstemp(suffix=".csv")
        os.close(db_fd)
        os.close(out_fd)

        try:
            mock_html_resp = MagicMock()
            mock_html_resp.read.return_value = SAMPLE_HTML.encode('utf-8')
            mock_html_resp.__enter__.return_value = mock_html_resp

            mock_csv_resp = MagicMock()
            mock_csv_resp.read.return_value = SAMPLE_CSV.encode('utf-8-sig')
            mock_csv_resp.__enter__.return_value = mock_csv_resp

            mock_urlopen.side_effect = [mock_html_resp, mock_csv_resp]

            # 1. import コマンド実行
            with patch('sys.argv', ['main.py', 'import', '-f', '120', '--db', db_path]):
                main.main()

            db = Database(db_path)
            to_scrape = db.get_facilities_to_scrape()
            self.assertEqual(len(to_scrape), 1)
            self.assertEqual(to_scrape[0]["facility_name"], "訪問入浴テスト")

            # 2. export コマンド実行
            with patch('sys.argv', ['main.py', 'export', '-f', '120', '-o', out_path, '--db', db_path]):
                main.main()

            self.assertTrue(os.path.exists(out_path))

        finally:
            if os.path.exists(db_path):
                os.remove(db_path)
            if os.path.exists(out_path):
                os.remove(out_path)

if __name__ == '__main__':
    unittest.main()
