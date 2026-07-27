import argparse
import datetime
import os
import shutil
import sqlite3
from typing import List, Dict, Optional

DEFAULT_DB_PATH = "kaigo.db"
DEFAULT_BACKUP_DIR = "backup"

def get_backup_filepath(backup_dir: str = DEFAULT_BACKUP_DIR, db_name: str = "kaigo") -> str:
    now_str = datetime.datetime.now().strftime("%Y%m%m_%H%M%S")
    os.makedirs(backup_dir, exist_ok=True)
    filename = f"backup_{db_name}_{now_str}.db"
    return os.path.join(backup_dir, filename)

def create_backup(db_path: str = DEFAULT_DB_PATH, backup_dir: str = DEFAULT_BACKUP_DIR) -> str:
    """SQLiteオンラインバックアップAPIを利用して整合性を保ったDBバックアップを作成"""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"データベースファイル '{db_path}' が存在しません。")

    db_base_name = os.path.splitext(os.path.basename(db_path))[0]
    target_path = get_backup_filepath(backup_dir=backup_dir, db_name=db_base_name)

    # sqlite3 の backup API を使用（読み書き中でも破損しない安全なオンラインバックアップ）
    src_conn = sqlite3.connect(db_path)
    dst_conn = sqlite3.connect(target_path)
    try:
        with dst_conn:
            src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    size_bytes = os.path.getsize(target_path)
    size_mb = size_bytes / (1024 * 1024)
    print(f"✅ バックアップを作成しました:")
    print(f"   ・保存先: {target_path}")
    print(f"   ・サイズ: {size_mb:.2f} MB ({size_bytes:,} bytes)")

    return target_path

def list_backups(backup_dir: str = DEFAULT_BACKUP_DIR) -> List[Dict[str, str]]:
    """バックアップ一覧を取得・表示"""
    if not os.path.exists(backup_dir):
        print(f"バックアップフォルダ '{backup_dir}' はまだ存在しません。")
        return []

    files = [f for f in os.listdir(backup_dir) if f.endswith(".db")]
    if not files:
        print(f"バックアップフォルダ '{backup_dir}' 内にバックアップファイルはありません。")
        return []

    backups = []
    for f in sorted(files, reverse=True):
        full_path = os.path.join(backup_dir, f)
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(full_path))
        size_mb = os.path.getsize(full_path) / (1024 * 1024)
        backups.append({
            "filename": f,
            "filepath": full_path,
            "mtime": mtime.strftime("%Y-%m-%d %H:%M:%S"),
            "size_mb": f"{size_mb:.2f} MB"
        })

    print("=" * 65)
    print("                     作成済みバックアップ一覧")
    print("=" * 65)
    print(f"  {'ファイル名':<35} {'作成日時':<20} {'サイズ':>10}")
    print("  " + "-" * 63)
    for b in backups:
        print(f"  {b['filename']:<35} {b['mtime']:<20} {b['size_mb']:>10}")
    print("=" * 65)

    return backups

def restore_backup(
    file_identifier: str,
    db_path: str = DEFAULT_DB_PATH,
    backup_dir: str = DEFAULT_BACKUP_DIR
) -> bool:
    """指定されたバックアップファイルからDBを復元"""
    # ファイル指定の評価（絶対パス / 相対パス / ファイル名のみ）
    candidate_paths = [
        file_identifier,
        os.path.join(backup_dir, file_identifier),
        os.path.join(backup_dir, os.path.basename(file_identifier))
    ]

    target_backup = None
    for p in candidate_paths:
        if os.path.exists(p) and os.path.isfile(p):
            target_backup = p
            break

    if not target_backup:
        print(f"❌ 指定されたバックアップファイル '{file_identifier}' が見つかりませんでした。")
        print("`python main.py backup` コマンドで存在するファイル名をご確認ください。")
        return False

    # 既存DBが存在する場合、安全のための事前テンポラリ退避
    if os.path.exists(db_path):
        pre_restore_safety = f"{db_path}.before_restore"
        shutil.copy2(db_path, pre_restore_safety)

    try:
        src_conn = sqlite3.connect(target_backup)
        dst_conn = sqlite3.connect(db_path)
        try:
            with dst_conn:
                src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
            src_conn.close()

        # 退避ファイルを削除
        if os.path.exists(f"{db_path}.before_restore"):
            os.remove(f"{db_path}.before_restore")

        print(f"✅ データベースを復元しました:")
        print(f"   ・復元元: {target_backup}")
        print(f"   ・復元先: {db_path}")
        return True

    except Exception as e:
        print(f"❌ 復元中にエラーが発生しました: {e}")
        # 退避ファイルがあれば元に戻す
        if os.path.exists(f"{db_path}.before_restore"):
            shutil.move(f"{db_path}.before_restore", db_path)
            print("   -> 復元前のデータベース状態にロールバックしました。")
        return False

def main():
    parser = argparse.ArgumentParser(description="データベースのバックアップ作成・一覧・復元を行います")
    subparsers = parser.add_subparsers(dest="action", help="処理を選択してください")

    # 1. create
    p_create = subparsers.add_parser("create", help="バックアップを作成")
    p_create.add_argument("--db", default=DEFAULT_DB_PATH, help="対象データベースファイル")
    p_create.add_argument("--dir", default=DEFAULT_BACKUP_DIR, help="バックアップ保存先フォルダ")

    # 2. list
    p_list = subparsers.add_parser("list", help="バックアップ一覧を表示")
    p_list.add_argument("--dir", default=DEFAULT_BACKUP_DIR, help="バックアップ保存先フォルダ")

    # 3. restore
    p_restore = subparsers.add_parser("restore", help="バックアップファイルから復元")
    p_restore.add_argument("-f", "--file", required=True, help="復元元バックアップファイル名")
    p_restore.add_argument("--db", default=DEFAULT_DB_PATH, help="復元先データベースファイル")
    p_restore.add_argument("--dir", default=DEFAULT_BACKUP_DIR, help="バックアップ保存先フォルダ")

    args = parser.parse_args()

    if args.action == "create" or args.action is None:
        create_backup(db_path=getattr(args, "db", DEFAULT_DB_PATH), backup_dir=getattr(args, "dir", DEFAULT_BACKUP_DIR))
        list_backups(backup_dir=getattr(args, "dir", DEFAULT_BACKUP_DIR))
    elif args.action == "list":
        list_backups(backup_dir=args.dir)
    elif args.action == "restore":
        restore_backup(file_identifier=args.file, db_path=args.db, backup_dir=args.dir)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
