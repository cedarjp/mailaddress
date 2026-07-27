import os
import shutil
import tempfile
import unittest
from db import Database
from backup import create_backup, list_backups, restore_backup

class TestBackupRestore(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_kaigo.db")
        self.backup_dir = os.path.join(self.tmp_dir, "backup")

        # テスト用初期DB作成
        db = Database(self.db_path)
        db.init_db()
        fid = db.register_source_file("test_ident", "test.csv", "http://example.com")
        db.insert_facilities(fid, [{"code": "001", "facility_name": "初期施設A", "url": "http://a.com"}])

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_backup_and_restore(self):
        # 1. バックアップ作成
        backup_file = create_backup(db_path=self.db_path, backup_dir=self.backup_dir)
        self.assertTrue(os.path.exists(backup_file))

        # バックアップ一覧取得テスト
        backups = list_backups(backup_dir=self.backup_dir)
        self.assertEqual(len(backups), 1)

        # 2. 元DBに新しいデータを追加してDB内容を更新
        db = Database(self.db_path)
        fid = db.register_source_file("test_ident2", "test2.csv", "http://example2.com")
        db.insert_facilities(fid, [{"code": "002", "facility_name": "更新施設B", "url": "http://b.com"}])

        # 変更後、事業所数が2件あることを確認
        facilities_after = db.export_combined_data()
        self.assertEqual(len(facilities_after), 2)

        # 3. バックアップからリストア（復元）
        backup_filename = os.path.basename(backup_file)
        restored = restore_backup(file_identifier=backup_filename, db_path=self.db_path, backup_dir=self.backup_dir)
        self.assertTrue(restored)

        # 4. 復元後、初期状態の1件に戻っていることを確認
        facilities_restored = db.export_combined_data()
        self.assertEqual(len(facilities_restored), 1)
        self.assertEqual(facilities_restored[0]["事業所名"], "初期施設A")

if __name__ == "__main__":
    unittest.main()
