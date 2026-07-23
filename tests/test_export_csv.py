import csv
import os
import tempfile
import unittest
from db import Database
from export_csv import export_facilities_to_csv, CSV_HEADER

class TestExportCSV(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.db = Database(self.db_path)
        self.db.init_db()

        # ダミーデータの投入
        file_id_1 = self.db.register_source_file("110_訪問介護", "jigyosho_110.csv", "https://example.com/110.csv")
        file_id_2 = self.db.register_source_file("120_訪問入浴", "jigyosho_120.csv", "https://example.com/120.csv")

        rec1 = {
            "code": "011011",
            "pref_name": "北海道",
            "city_name": "札幌市中央区",
            "facility_name": "事業所1",
            "url": "http://example1.com"
        }
        rec2 = {
            "code": "131016",
            "pref_name": "東京都",
            "city_name": "千代田区",
            "facility_name": "事業所2",
            "url": "http://example2.com"
        }

        self.db.insert_facilities(file_id_1, [rec1])
        self.db.insert_facilities(file_id_2, [rec2])

        facs = self.db.get_facilities_to_scrape()
        for fac in facs:
            if fac["facility_name"] == "事業所1":
                self.db.add_emails(fac["id"], [("info@example1.com", "http://example1.com/contact")])

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_export_all(self):
        out_fd, out_path = tempfile.mkstemp(suffix=".csv")
        os.close(out_fd)

        try:
            count = export_facilities_to_csv(db_path=self.db_path, output_file=out_path)
            self.assertEqual(count, 2)

            with open(out_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                rows = list(reader)
                self.assertEqual(len(rows), 3) # ヘッダー + 2件
                self.assertEqual(rows[0], CSV_HEADER)
                self.assertIn("info@example1.com", rows[1] + rows[2])
        finally:
            if os.path.exists(out_path):
                os.remove(out_path)

    def test_export_with_filter(self):
        out_fd, out_path = tempfile.mkstemp(suffix=".csv")
        os.close(out_fd)

        try:
            count = export_facilities_to_csv(
                db_path=self.db_path,
                output_file=out_path,
                pref="東京都"
            )
            self.assertEqual(count, 1)

            with open(out_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                rows = list(reader)
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[1][4], "事業所2") # 事業所名
        finally:
            if os.path.exists(out_path):
                os.remove(out_path)

if __name__ == '__main__':
    unittest.main()
