import argparse
from typing import Optional
from db import Database

def display_status(
    db_path: str = "kaigo.db",
    file_filter: Optional[str] = None,
    code: Optional[str] = None,
    pref: Optional[str] = None,
    city: Optional[str] = None
):
    db = Database(db_path)
    db.init_db()

    summary = db.get_summary_stats(
        file_identifier=file_filter,
        code=code,
        pref_name=pref,
        city_name=city
    )

    by_file = db.get_stats_by_file(
        file_identifier=file_filter,
        code=code,
        pref_name=pref,
        city_name=city
    )

    by_pref = db.get_stats_by_pref(
        file_identifier=file_filter,
        code=code,
        pref_name=pref,
        city_name=city,
        limit=10
    )

    total_fac = summary["total_facilities"]
    url_count = summary["url_count"]
    pending = summary["pending_count"]
    completed = summary["completed_count"]
    no_email = summary["no_email_count"]
    no_url = summary["no_url_count"]
    failed = summary["failed_count"]

    processed = completed + no_email + failed
    progress_rate = (processed / url_count * 100) if url_count > 0 else 0.0
    email_success_rate = (summary["facilities_with_email"] / processed * 100) if processed > 0 else 0.0

    print("=" * 65)
    print("           介護企業データ & メール収集スクレイピング進捗状況")
    print("=" * 65)

    filters = []
    if file_filter: filters.append(f"ファイル/サービス: '{file_filter}'")
    if code: filters.append(f"地域コード: '{code}'")
    if pref: filters.append(f"都道府県: '{pref}'")
    if city: filters.append(f"市区町村: '{city}'")

    if filters:
        print("【絞り込み条件】: " + " / ".join(filters))
        print("-" * 65)

    print("【全体サマリー】")
    print(f"  ・登録事業所総数          : {total_fac:,} 件")
    print(f"  ・URL記載あり (対象)     : {url_count:,} 件 ({url_count / total_fac * 100:.1f}%)" if total_fac > 0 else "  ・URL記載あり (対象)     : 0 件")
    print(f"  ・URL記載なし (対象外)   : {no_url:,} 件")
    print(f"  ・スクレイピング進捗     : {processed:,} / {url_count:,} 件 ({progress_rate:.1f}%)")
    print(f"     - 完了 (メール発見)   : {completed:,} 件")
    print(f"     - 完了 (メールなし)   : {no_email:,} 件")
    print(f"     - 失敗 (エラー等)      : {failed:,} 件")
    print(f"     - 未処理 (Pending)    : {pending:,} 件")
    print(f"  ・収集済みメールアドレス  : {summary['unique_emails']:,} 件 (ユニーク)")
    print(f"  ・メール獲得成功率       : {email_success_rate:.1f}% (獲得済: {summary['facilities_with_email']:,} 事業所 / 処理済: {processed:,} 事業所)")
    print("-" * 65)

    if by_file:
        print("【サービス（ファイル）別内訳】")
        print(f"  {'ファイル識別子':<24} {'総件数':>8} {'処理済':>8} {'メール数':>8} {'獲得率':>8}")
        print("  " + "-" * 60)
        for r in by_file:
            ident = r["file_identifier"][:24]
            total = r["total_count"]
            proc = r["processed_count"]
            emails = r["email_count"]
            succ = r["success_count"]
            rate = (succ / proc * 100) if proc > 0 else 0.0
            print(f"  {ident:<24} {total:>8,} {proc:>8,} {emails:>8,} {rate:>7.1f}%")
        print("-" * 65)

    if by_pref and not pref:
        print("【都道府県別内訳 (Top 10)】")
        print(f"  {'都道府県名':<12} {'総件数':>8} {'処理済':>8} {'メール数':>8}")
        print("  " + "-" * 42)
        for r in by_pref:
            pname = r["pref_name"][:12]
            total = r["total_count"]
            proc = r["processed_count"]
            emails = r["email_count"]
            print(f"  {pname:<12} {total:>8,} {proc:>8,} {emails:>8,}")
        print("=" * 65)

def main():
    parser = argparse.ArgumentParser(description="介護事業所データおよびメール収集の進捗状況を表示します")
    parser.add_argument("-f", "--file", help="取り込みファイル識別子またはファイル名（例: 110_訪問介護）")
    parser.add_argument("--code", help="都道府県コード又は市町村コード")
    parser.add_argument("--pref", help="都道府県名")
    parser.add_argument("--city", help="市区町村名")
    parser.add_argument("--db", default="kaigo.db", help="SQLiteデータベースファイルパス")

    args = parser.parse_args()

    display_status(
        db_path=args.db,
        file_filter=args.file,
        code=args.code,
        pref=args.pref,
        city=args.city
    )

if __name__ == "__main__":
    main()
