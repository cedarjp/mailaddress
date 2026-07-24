import sqlite3
from typing import Optional, List, Dict, Any, Tuple
import os

CREATE_SOURCE_FILES_TABLE = """
CREATE TABLE IF NOT EXISTS source_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_identifier TEXT UNIQUE NOT NULL,
    file_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    imported_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_FACILITIES_TABLE = """
CREATE TABLE IF NOT EXISTS facilities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file_id INTEGER NOT NULL,
    code TEXT,
    no TEXT,
    pref_name TEXT,
    city_name TEXT,
    facility_name TEXT,
    facility_kana TEXT,
    service_type TEXT,
    address TEXT,
    building TEXT,
    lat REAL,
    lng REAL,
    tel TEXT,
    fax TEXT,
    corporate_no TEXT,
    corporate_name TEXT,
    facility_no TEXT,
    available_days TEXT,
    available_days_note TEXT,
    capacity TEXT,
    url TEXT,
    shared_service TEXT,
    kaigo_standard TEXT,
    shogai_standard TEXT,
    remarks TEXT,
    scrape_status TEXT DEFAULT 'pending',
    scraped_at DATETIME,
    FOREIGN KEY (source_file_id) REFERENCES source_files (id)
);
"""

CREATE_EMAILS_TABLE = """
CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_id INTEGER NOT NULL,
    email TEXT NOT NULL,
    source_page_url TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (facility_id) REFERENCES facilities (id),
    UNIQUE (facility_id, email)
);
"""

CREATE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_facilities_code ON facilities (code);
CREATE INDEX IF NOT EXISTS idx_facilities_pref ON facilities (pref_name);
CREATE INDEX IF NOT EXISTS idx_facilities_city ON facilities (city_name);
CREATE INDEX IF NOT EXISTS idx_facilities_scrape_status ON facilities (scrape_status);
CREATE INDEX IF NOT EXISTS idx_source_files_identifier ON source_files (file_identifier);
"""

class Database:
    def __init__(self, db_path: str = "kaigo.db"):
        self.db_path = db_path

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """データベースの初期化とテーブル・インデックスの作成"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(CREATE_SOURCE_FILES_TABLE)
            cursor.execute(CREATE_FACILITIES_TABLE)
            cursor.execute(CREATE_EMAILS_TABLE)
            cursor.executescript(CREATE_INDEXES)
            conn.commit()

    def register_source_file(self, file_identifier: str, file_name: str, source_url: str) -> int:
        """ソースファイルを登録してそのIDを返す。既に存在する場合は既存IDを返す。"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM source_files WHERE file_identifier = ?",
                (file_identifier,)
            )
            row = cursor.fetchone()
            if row:
                return row["id"]

            cursor.execute(
                """
                INSERT INTO source_files (file_identifier, file_name, source_url)
                VALUES (?, ?, ?)
                """,
                (file_identifier, file_name, source_url)
            )
            conn.commit()
            return cursor.lastrowid

    def insert_facilities(self, source_file_id: int, records: List[Dict[str, Any]]) -> int:
        """事業者データのリストを一括挿入する"""
        if not records:
            return 0

        columns = [
            "source_file_id", "code", "no", "pref_name", "city_name",
            "facility_name", "facility_kana", "service_type", "address",
            "building", "lat", "lng", "tel", "fax", "corporate_no",
            "corporate_name", "facility_no", "available_days",
            "available_days_note", "capacity", "url", "shared_service",
            "kaigo_standard", "shogai_standard", "remarks", "scrape_status"
        ]

        placeholders = ", ".join(["?"] * len(columns))
        col_string = ", ".join(columns)
        sql = f"INSERT INTO facilities ({col_string}) VALUES ({placeholders})"

        values = []
        for rec in records:
            url_val = (rec.get("url") or "").strip()
            # URLが存在しないか不適切な場合はステータスを'no_url'に設定
            status = 'pending' if (url_val and url_val.lower().startswith(('http://', 'https://'))) else 'no_url'

            def to_float(v):
                try:
                    return float(v) if v else None
                except (ValueError, TypeError):
                    return None

            row_vals = [
                source_file_id,
                rec.get("code"),
                rec.get("no"),
                rec.get("pref_name"),
                rec.get("city_name"),
                rec.get("facility_name"),
                rec.get("facility_kana"),
                rec.get("service_type"),
                rec.get("address"),
                rec.get("building"),
                to_float(rec.get("lat")),
                to_float(rec.get("lng")),
                rec.get("tel"),
                rec.get("fax"),
                rec.get("corporate_no"),
                rec.get("corporate_name"),
                rec.get("facility_no"),
                rec.get("available_days"),
                rec.get("available_days_note"),
                rec.get("capacity"),
                url_val,
                rec.get("shared_service"),
                rec.get("kaigo_standard"),
                rec.get("shogai_standard"),
                rec.get("remarks"),
                status
            ]
            values.append(row_vals)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, values)
            conn.commit()
            return cursor.rowcount

    def get_facilities_to_scrape(
        self,
        file_identifier: Optional[str] = None,
        code: Optional[str] = None,
        pref_name: Optional[str] = None,
        city_name: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[sqlite3.Row]:
        """スクレイピング対象の事業所を取得（pendingかつ有効なURLを持つもの）"""
        query = """
        SELECT f.*
        FROM facilities f
        JOIN source_files sf ON f.source_file_id = sf.id
        WHERE f.scrape_status = 'pending'
          AND f.url IS NOT NULL
          AND f.url != ''
        """
        params = []

        if file_identifier:
            query += " AND (sf.file_identifier LIKE ? OR sf.file_name LIKE ?)"
            params.extend([f"%{file_identifier}%", f"%{file_identifier}%"])

        if code:
            query += " AND f.code = ?"
            params.append(code)

        if pref_name:
            query += " AND f.pref_name LIKE ?"
            params.append(f"%{pref_name}%")

        if city_name:
            query += " AND f.city_name LIKE ?"
            params.append(f"%{city_name}%")

        query += " ORDER BY f.id ASC"

        if limit and limit > 0:
            query += " LIMIT ?"
            params.append(limit)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

    def add_emails(self, facility_id: int, emails: List[Tuple[str, str]]) -> int:
        """メールアドレスを登録（(email, source_page_url)のリスト）"""
        if not emails:
            return 0

        sql = """
        INSERT OR IGNORE INTO emails (facility_id, email, source_page_url)
        VALUES (?, ?, ?)
        """
        values = [(facility_id, email, url) for email, url in emails]

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, values)
            conn.commit()
            return cursor.rowcount

    def update_facility_scrape_status(self, facility_id: int, status: str):
        """事業所のスクレイピングステータスを更新"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE facilities
                SET scrape_status = ?, scraped_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, facility_id)
            )
            conn.commit()

    def export_combined_data(
        self,
        file_identifier: Optional[str] = None,
        code: Optional[str] = None,
        pref_name: Optional[str] = None,
        city_name: Optional[str] = None
    ) -> List[sqlite3.Row]:
        """絞り込み条件に従って事業所情報と抽出メールアドレスを結合取得"""
        query = """
        SELECT 
            f.code AS 都道府県コード又は市町村コード,
            f.no AS No,
            f.pref_name AS 都道府県名,
            f.city_name AS 市区町村名,
            f.facility_name AS 事業所名,
            f.facility_kana AS 事業所名カナ,
            f.service_type AS サービスの種類,
            f.address AS 住所,
            f.building AS 方書（ビル名等）,
            f.lat AS 緯度,
            f.lng AS 経度,
            f.tel AS 電話番号,
            f.fax AS FAX番号,
            f.corporate_no AS 法人番号,
            f.corporate_name AS 法人の名称,
            f.facility_no AS 事業所番号,
            f.available_days AS 利用可能曜日,
            f.available_days_note AS 利用可能曜日特記事項,
            f.capacity AS 定員,
            f.url AS URL,
            f.shared_service AS 高齢者の方と障害者の方が同時一体的に利用できるサービス,
            f.kaigo_standard AS 介護保険の通常の指定基準を満たしている,
            f.shogai_standard AS 障害福祉の通常の指定基準を満たしている,
            f.remarks AS 備考,
            sf.file_identifier AS 取り込みファイル識別子,
            sf.file_name AS 取り込みファイル名,
            e.email AS メールアドレス,
            e.source_page_url AS メール取得元URL
        FROM facilities f
        JOIN source_files sf ON f.source_file_id = sf.id
        LEFT JOIN emails e ON f.id = e.facility_id
        WHERE 1=1
        """
        params = []

        if file_identifier:
            query += " AND (sf.file_identifier LIKE ? OR sf.file_name LIKE ?)"
            params.extend([f"%{file_identifier}%", f"%{file_identifier}%"])

        if code:
            query += " AND f.code = ?"
            params.append(code)

        if pref_name:
            query += " AND f.pref_name LIKE ?"
            params.append(f"%{pref_name}%")

        if city_name:
            query += " AND f.city_name LIKE ?"
            params.append(f"%{city_name}%")

        query += " ORDER BY f.id ASC"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

    def get_summary_stats(
        self,
        file_identifier: Optional[str] = None,
        code: Optional[str] = None,
        pref_name: Optional[str] = None,
        city_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """全体ステータスのサマリーを取得"""
        where_clause = " WHERE 1=1"
        params = []

        if file_identifier:
            where_clause += " AND (sf.file_identifier LIKE ? OR sf.file_name LIKE ?)"
            params.extend([f"%{file_identifier}%", f"%{file_identifier}%"])
        if code:
            where_clause += " AND f.code = ?"
            params.append(code)
        if pref_name:
            where_clause += " AND f.pref_name LIKE ?"
            params.append(f"%{pref_name}%")
        if city_name:
            where_clause += " AND f.city_name LIKE ?"
            params.append(f"%{city_name}%")

        query = f"""
        SELECT
            COUNT(f.id) AS total_facilities,
            SUM(CASE WHEN f.url IS NOT NULL AND f.url != '' THEN 1 ELSE 0 END) AS url_count,
            SUM(CASE WHEN f.scrape_status = 'pending' AND f.url IS NOT NULL AND f.url != '' THEN 1 ELSE 0 END) AS pending_count,
            SUM(CASE WHEN f.scrape_status = 'completed' THEN 1 ELSE 0 END) AS completed_count,
            SUM(CASE WHEN f.scrape_status = 'no_email' THEN 1 ELSE 0 END) AS no_email_count,
            SUM(CASE WHEN f.scrape_status = 'no_url' THEN 1 ELSE 0 END) AS no_url_count,
            SUM(CASE WHEN f.scrape_status = 'failed' THEN 1 ELSE 0 END) AS failed_count
        FROM facilities f
        JOIN source_files sf ON f.source_file_id = sf.id
        {where_clause}
        """

        email_query = f"""
        SELECT
            COUNT(DISTINCT e.email) AS unique_emails,
            COUNT(DISTINCT e.facility_id) AS facilities_with_email
        FROM emails e
        JOIN facilities f ON e.facility_id = f.id
        JOIN source_files sf ON f.source_file_id = sf.id
        {where_clause}
        """

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()

            cursor.execute(email_query, params)
            email_row = cursor.fetchone()

            return {
                "total_facilities": row["total_facilities"] or 0,
                "url_count": row["url_count"] or 0,
                "pending_count": row["pending_count"] or 0,
                "completed_count": row["completed_count"] or 0,
                "no_email_count": row["no_email_count"] or 0,
                "no_url_count": row["no_url_count"] or 0,
                "failed_count": row["failed_count"] or 0,
                "unique_emails": email_row["unique_emails"] or 0,
                "facilities_with_email": email_row["facilities_with_email"] or 0,
            }

    def get_stats_by_file(
        self,
        file_identifier: Optional[str] = None,
        code: Optional[str] = None,
        pref_name: Optional[str] = None,
        city_name: Optional[str] = None
    ) -> List[sqlite3.Row]:
        """ファイル識別子ごとの内訳を取得"""
        where_clause = " WHERE 1=1"
        params = []

        if file_identifier:
            where_clause += " AND (sf.file_identifier LIKE ? OR sf.file_name LIKE ?)"
            params.extend([f"%{file_identifier}%", f"%{file_identifier}%"])
        if code:
            where_clause += " AND f.code = ?"
            params.append(code)
        if pref_name:
            where_clause += " AND f.pref_name LIKE ?"
            params.append(f"%{pref_name}%")
        if city_name:
            where_clause += " AND f.city_name LIKE ?"
            params.append(f"%{city_name}%")

        query = f"""
        SELECT
            sf.file_identifier,
            COUNT(f.id) AS total_count,
            SUM(CASE WHEN f.scrape_status IN ('completed', 'no_email', 'failed') THEN 1 ELSE 0 END) AS processed_count,
            SUM(CASE WHEN f.scrape_status = 'completed' THEN 1 ELSE 0 END) AS success_count,
            COUNT(DISTINCT e.email) AS email_count
        FROM source_files sf
        JOIN facilities f ON f.source_file_id = sf.id
        LEFT JOIN emails e ON f.id = e.facility_id
        {where_clause}
        GROUP BY sf.file_identifier
        ORDER BY total_count DESC
        """

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

    def get_stats_by_pref(
        self,
        file_identifier: Optional[str] = None,
        code: Optional[str] = None,
        pref_name: Optional[str] = None,
        city_name: Optional[str] = None,
        limit: int = 10
    ) -> List[sqlite3.Row]:
        """都道府県ごとの内訳を取得"""
        where_clause = " WHERE 1=1"
        params = []

        if file_identifier:
            where_clause += " AND (sf.file_identifier LIKE ? OR sf.file_name LIKE ?)"
            params.extend([f"%{file_identifier}%", f"%{file_identifier}%"])
        if code:
            where_clause += " AND f.code = ?"
            params.append(code)
        if pref_name:
            where_clause += " AND f.pref_name LIKE ?"
            params.append(f"%{pref_name}%")
        if city_name:
            where_clause += " AND f.city_name LIKE ?"
            params.append(f"%{city_name}%")

        query = f"""
        SELECT
            COALESCE(f.pref_name, '不明') AS pref_name,
            COUNT(f.id) AS total_count,
            SUM(CASE WHEN f.scrape_status IN ('completed', 'no_email', 'failed') THEN 1 ELSE 0 END) AS processed_count,
            COUNT(DISTINCT e.email) AS email_count
        FROM facilities f
        JOIN source_files sf ON f.source_file_id = sf.id
        LEFT JOIN emails e ON f.id = e.facility_id
        {where_clause}
        GROUP BY f.pref_name
        ORDER BY total_count DESC
        LIMIT ?
        """
        params.append(limit)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

