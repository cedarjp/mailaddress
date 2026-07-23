import os
import tempfile
import pytest
from db import Database

@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    db = Database(db_path)
    db.init_db()
    yield db
    if os.path.exists(db_path):
        os.remove(db_path)

def test_init_db(temp_db):
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row["name"] for row in cursor.fetchall()]
        assert "source_files" in tables
        assert "facilities" in tables
        assert "emails" in tables

def test_register_source_file(temp_db):
    file_id = temp_db.register_source_file("110_訪問介護", "jigyosho_110.csv", "https://example.com/jigyosho_110.csv")
    assert file_id > 0

    # 重複登録時に既存IDが返ることを確認
    file_id_2 = temp_db.register_source_file("110_訪問介護", "jigyosho_110.csv", "https://example.com/jigyosho_110.csv")
    assert file_id == file_id_2

def test_insert_and_get_facilities(temp_db):
    file_id = temp_db.register_source_file("110_訪問介護", "jigyosho_110.csv", "https://example.com/jigyosho_110.csv")
    records = [
        {
            "code": "011011",
            "no": "001",
            "pref_name": "北海道",
            "city_name": "札幌市中央区",
            "facility_name": "テスト事業所A",
            "url": "http://example-a.com"
        },
        {
            "code": "011012",
            "no": "002",
            "pref_name": "北海道",
            "city_name": "札幌市北区",
            "facility_name": "テスト事業所B",
            "url": ""
        }
    ]
    inserted = temp_db.insert_facilities(file_id, records)
    assert inserted == 2

    # pending の事業所だけが取得されるか
    to_scrape = temp_db.get_facilities_to_scrape()
    assert len(to_scrape) == 1
    assert to_scrape[0]["facility_name"] == "テスト事業所A"

def test_emails_and_export(temp_db):
    file_id = temp_db.register_source_file("110_訪問介護", "jigyosho_110.csv", "https://example.com/jigyosho_110.csv")
    records = [{
        "code": "011011",
        "pref_name": "北海道",
        "city_name": "札幌市中央区",
        "facility_name": "テスト事業所A",
        "url": "http://example-a.com"
    }]
    temp_db.insert_facilities(file_id, records)
    to_scrape = temp_db.get_facilities_to_scrape()
    fac_id = to_scrape[0]["id"]

    added = temp_db.add_emails(fac_id, [("info@example-a.com", "http://example-a.com/contact")])
    assert added == 1

    temp_db.update_facility_scrape_status(fac_id, "completed")

    exported = temp_db.export_combined_data(file_identifier="110")
    assert len(exported) == 1
    assert exported[0]["メールアドレス"] == "info@example-a.com"
    assert exported[0]["事業所名"] == "テスト事業所A"
