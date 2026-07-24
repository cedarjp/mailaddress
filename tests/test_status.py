import os
import tempfile
import unittest
from db import Database
from status import display_status

class TestStatus(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.db = Database(self.db_path)
        self.db.init_db()

        file_id = self.db.register_source_file("110_訪問介護", "jigyosho_110.csv", "https://example.com/110.csv")
        records = [
            {"code": "011011", "pref_name": "北海道", "city_name": "札幌市中央区", "facility_name": "施設A", "url": "http://a.com"},
            {"code": "011011", "pref_name": "北海道", "city_name": "札幌市中央区", "facility_name": "施設B", "url": "http://b.com"},
            {"code": "131016", "pref_name": "東京都", "city_name": "千代田区", "facility_name": "施設C", "url": ""},
        ]
        self.db.insert_facilities(file_id, records)

        facs = self.db.get_facilities_to_scrape()
        # 施設Aをcompletedにしてメール追加
        for fac in facs:
            if fac["facility_name"] == "施設A":
                self.db.add_emails(fac["id"], [("info@a.com", "http://a.com")])
                self.db.update_facility_scrape_status(fac["id"], "completed")

    def tearDown(self):
        os.close(self.db_fd)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_summary_stats(self):
        stats = self.db.get_summary_stats()
        self.assertEqual(stats["total_facilities"], 3)
        self.assertEqual(stats["url_count"], 2)
        self.assertEqual(stats["completed_count"], 1)
        self.assertEqual(stats["pending_count"], 1)
        self.assertEqual(stats["no_url_count"], 1)
        self.assertEqual(stats["unique_emails"], 1)

    def test_display_status(self):
        # 例外なく実行完了できるか検証
        try:
            display_status(db_path=self.db_path)
            display_status(db_path=self.db_path, pref="北海道")
        except Exception as e:
            self.fail(f"display_status raised exception: {e}")

if __name__ == "__main__":
    unittest.main()
