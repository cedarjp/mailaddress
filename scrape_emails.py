import argparse
import asyncio
import gc
import re
import sys
import time
import urllib.parse
from typing import List, Set, Tuple, Optional
from playwright.async_api import async_playwright, Page, BrowserContext

from db import Database

# Windows環境でのクラッシュポップアップ（WerFault.exe / 動作を停止しましたダイアログ）を無効化
if sys.platform == "win32":
    try:
        import ctypes
        # SEM_FAILCRITICALERRORS (0x0001) | SEM_NOGPFAULTERRORBOX (0x0002)
        ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002)
    except Exception:
        pass

# メールアドレス正規表現
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

# 除外パターン（誤検出防止）
EXCLUDE_EMAIL_PATTERNS = [
    r'^example@', r'^user@', r'^test@', r'^domain@',
    r'\.(png|jpg|jpeg|gif|css|js|svg)@', r'^name@'
]

# お問い合わせ系リンク優先キーワード
PRIORITY_KEYWORDS = ['問合', '問い合わせ', 'お問合せ', 'contact', 'about', '会社', '概要', 'アクセス', '情報', 'プライバシー']

def is_valid_email(email: str) -> bool:
    email_lower = email.lower()
    for pattern in EXCLUDE_EMAIL_PATTERNS:
        if re.search(pattern, email_lower):
            return False
    return True

def extract_emails_from_text(text: str) -> Set[str]:
    found = set(EMAIL_REGEX.findall(text))
    valid_emails = {e for e in found if is_valid_email(e)}
    return valid_emails

def extract_emails_from_links(links: List[str]) -> Set[str]:
    emails = set()
    for link in links:
        if link.lower().startswith('mailto:'):
            raw_email = link[7:].split('?')[0].strip()
            if EMAIL_REGEX.match(raw_email) and is_valid_email(raw_email):
                emails.add(raw_email)
    return emails

def get_base_domain(url: str) -> str:
    """URLからドメイン部分を取り出し、www.を除去して正規化"""
    netloc = urllib.parse.urlparse(url).netloc.lower()
    if netloc.startswith('www.'):
        netloc = netloc[4:]
    return netloc

async def extract_links_from_page(page: Page, base_domains: Set[str]) -> List[str]:
    """ページ内の同一ドメインのリンクを取得"""
    try:
        elements = await page.query_selector_all('a[href]')
        hrefs = []
        for elem in elements:
            href = await elem.get_attribute('href')
            text = (await elem.inner_text() or '').strip()
            if href:
                full_url = urllib.parse.urljoin(page.url, href)
                parsed = urllib.parse.urlparse(full_url)
                target_domain = get_base_domain(full_url)
                # HTTP/HTTPS かつ許可ドメインのみに対象を絞る
                if parsed.scheme in ('http', 'https') and target_domain in base_domains:
                    hrefs.append((full_url, text))
        
        # 優先キーワードが含まれるリンクを前にソート
        def sort_key(item):
            url, txt = item
            for kw in PRIORITY_KEYWORDS:
                if kw in txt or kw in url:
                    return 0
            return 1

        hrefs.sort(key=sort_key)
        return [url for url, txt in hrefs]
    except Exception:
        return []

async def scrape_facility_emails(
    context: BrowserContext,
    start_url: str,
    interval: float = 1.0,
    max_pages: int = 10,
    max_depth: int = 2
) -> Tuple[List[Tuple[str, str]], str]:
    """
    1つの事業所ウェブサイトを再帰的にスクレイピングしてメールアドレスを抽出。
    メールが見つかったら即座に終了。
    戻り値: ([(email, source_url), ...], status_string)
    """
    visited: Set[str] = set()
    queue: List[Tuple[str, int]] = [(start_url, 0)]
    emails_found: Set[Tuple[str, str]] = set()

    page = await context.new_page()

    # JSのアラート/ダイアログが出ても即座に閉じてフリーズを防ぐ
    page.on("dialog", lambda dialog: asyncio.create_task(dialog.dismiss()))

    status = 'no_email'
    allowed_domains: Set[str] = {get_base_domain(start_url)}

    try:
        while queue and len(visited) < max_pages:
            current_url, depth = queue.pop(0)

            # URLの正規化
            clean_url = current_url.split('#')[0]
            if clean_url in visited:
                continue
            visited.add(clean_url)

            # 指定秒数のディレイ（サーバー負荷軽減）
            if len(visited) > 1 and interval > 0:
                await asyncio.sleep(interval)

            try:
                response = await page.goto(clean_url, wait_until='domcontentloaded', timeout=15000)
                if not response or response.status >= 400:
                    continue
                # リダイレクト後のドメインも許可対象に追加（例: http -> https や 別ドメイン移転対応）
                allowed_domains.add(get_base_domain(page.url))
            except Exception:
                continue

            # DOM全体テキストの取得（タイムアウト付き保護）
            try:
                content = await page.content()
                page_text = await page.inner_text('body') if await page.query_selector('body') else content
            except Exception:
                content = ""
                page_text = ""

            # テキストからのメール抽出
            extracted = extract_emails_from_text(page_text)
            
            # mailto: リンクからの抽出
            try:
                mailto_elements = await page.query_selector_all('a[href^="mailto:"]')
                mailto_hrefs = [await elem.get_attribute('href') for elem in mailto_elements if await elem.get_attribute('href')]
                mailto_emails = extract_emails_from_links(mailto_hrefs)
            except Exception:
                mailto_emails = set()
            
            all_page_emails = extracted.union(mailto_emails)

            if all_page_emails:
                for mail in all_page_emails:
                    emails_found.add((mail, page.url))
                status = 'completed'
                break  # メールが見つかった時点でこの事業所のスクレイピングを終了

            # メールが見つからず、まだ深さ上限に達していなければリンクをキューに追加
            if depth < max_depth:
                next_links = await extract_links_from_page(page, allowed_domains)
                for link in next_links:
                    if link.split('#')[0] not in visited:
                        queue.append((link, depth + 1))

    except Exception as e:
        if not emails_found:
            status = 'failed'
    finally:
        try:
            await page.close()
        except Exception:
            pass

    return list(emails_found), status

async def run_scraper(
    file_filter: Optional[str] = None,
    code: Optional[str] = None,
    pref: Optional[str] = None,
    city: Optional[str] = None,
    limit: Optional[int] = None,
    interval: float = 1.0,
    batch_size: int = 50,
    facility_timeout: float = 45.0,
    db_path: str = "kaigo.db",
    headless: bool = True
):
    db = Database(db_path)
    db.init_db()

    facilities = db.get_facilities_to_scrape(
        file_identifier=file_filter,
        code=code,
        pref_name=pref,
        city_name=city,
        limit=limit
    )

    if not facilities:
        print("対象となるスクレイピング未実行の事業所データが見つかりませんでした。")
        return

    total_count = len(facilities)
    print(f"対象事業所数: {total_count} 件 (バッチ再起動単位: {batch_size} 件ごと, 1事業所最大タイムアウト: {facility_timeout}秒)")

    # クラッシュ報告ダイアログ（WerFault）およびレンダラークラッシュの抑制フラグ
    chromium_args = [
        "--disable-breakpad",
        "--disable-crash-reporter",
        "--no-crash-upload",
        "--disable-gpu",
        "--disable-dev-shm-usage",
    ]

    async with async_playwright() as p:
        # batch_size 件ごとにブラウザインスタンスを再リフレッシュ（メモリ解放）
        for batch_start in range(0, total_count, batch_size):
            batch_items = facilities[batch_start:batch_start + batch_size]
            print(f"\n--- [ブラウザセッション開始: {batch_start + 1}〜{batch_start + len(batch_items)} / {total_count} 件] ---")

            try:
                browser = await p.chromium.launch(headless=headless, args=chromium_args)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )

                for idx, fac in enumerate(batch_items, batch_start + 1):
                    fac_id = fac["id"]
                    fac_name = fac["facility_name"]
                    url = fac["url"]

                    print(f"[{idx}/{total_count}] Processing: ID={fac_id}, {fac_name} ({url})...")

                    try:
                        # 1事業所のスクレイピング全体に対してタイムアウト保護を設定（ハング防止）
                        emails, status = await asyncio.wait_for(
                            scrape_facility_emails(context, url, interval=interval),
                            timeout=facility_timeout
                        )

                        if emails:
                            print(f"  -> Found {len(emails)} email(s): {[e[0] for e in emails]}")
                            db.add_emails(fac_id, emails)
                            db.update_facility_scrape_status(fac_id, 'completed')
                        else:
                            print(f"  -> No email found. Status: {status}")
                            db.update_facility_scrape_status(fac_id, status)

                    except asyncio.TimeoutError:
                        print(f"  -> Timed out ({facility_timeout}s exceeded). Skipping facility.")
                        db.update_facility_scrape_status(fac_id, 'failed')
                    except Exception as e:
                        print(f"  -> Error scraping {url}: {e}")
                        db.update_facility_scrape_status(fac_id, 'failed')

                # バッチ完了時にブラウザを閉じて明示的にガベージコレクションを実行
                try:
                    await context.close()
                    await browser.close()
                except Exception:
                    pass

            except Exception as batch_err:
                print(f"  -> Browser session error: {batch_err}")

            gc.collect()

    print("\nすべてのスクレイピング処理が完了しました。")

def main():
    parser = argparse.ArgumentParser(description="介護事業所WebサイトからPlaywrightを用いてメールアドレスを取得します")
    parser.add_argument("-f", "--file", help="取り込みファイル識別子またはファイル名（例: 110_訪問介護）")
    parser.add_argument("--code", help="都道府県コード又は市町村コード")
    parser.add_argument("--pref", help="都道府県名（例: 北海道）")
    parser.add_argument("--city", help="市区町村名（例: 札幌市中央区）")
    parser.add_argument("-n", "--limit", type=int, help="処理件数上限")
    parser.add_argument("--interval", type=float, default=1.0, help="ページ遷移ごとの待機秒数（デフォルト: 1.0秒）")
    parser.add_argument("-b", "--batch-size", type=int, default=50, help="ブラウザ再起動を行う件数単位（デフォルト: 50件）")
    parser.add_argument("--facility-timeout", type=float, default=45.0, help="1事業所あたりの全体最大タイムアウト秒数（デフォルト: 45秒）")
    parser.add_argument("--db", default="kaigo.db", help="SQLiteデータベースファイルパス")
    parser.add_argument("--head", action="store_true", help="ブラウザ画面を表示して実行")

    args = parser.parse_args()

    asyncio.run(run_scraper(
        file_filter=args.file,
        code=args.code,
        pref=args.pref,
        city=args.city,
        limit=args.limit,
        interval=args.interval,
        batch_size=args.batch_size,
        facility_timeout=args.facility_timeout,
        db_path=args.db,
        headless=not args.head
    ))

if __name__ == "__main__":
    main()
