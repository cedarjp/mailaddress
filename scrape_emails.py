import argparse
import asyncio
import re
import time
import urllib.parse
from typing import List, Set, Tuple, Optional
from playwright.async_api import async_playwright, Page, BrowserContext

from db import Database

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

async def extract_links_from_page(page: Page, base_url: str) -> List[str]:
    """ページ内の同一ドメインのリンクを取得"""
    base_domain = urllib.parse.urlparse(base_url).netloc
    try:
        elements = await page.query_selector_all('a[href]')
        hrefs = []
        for elem in elements:
            href = await elem.get_attribute('href')
            text = (await elem.inner_text() or '').strip()
            if href:
                full_url = urllib.parse.urljoin(page.url, href)
                parsed = urllib.parse.urlparse(full_url)
                # HTTP/HTTPS かつ同一ドメインのみに対象を絞る
                if parsed.scheme in ('http', 'https') and parsed.netloc == base_domain:
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
    status = 'no_email'

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
            except Exception:
                continue

            # DOM全体テキストの取得
            content = await page.content()
            page_text = await page.inner_text('body') if await page.query_selector('body') else content

            # テキストからのメール抽出
            extracted = extract_emails_from_text(page_text)
            
            # mailto: リンクからの抽出
            mailto_elements = await page.query_selector_all('a[href^="mailto:"]')
            mailto_hrefs = [await elem.get_attribute('href') for elem in mailto_elements if await elem.get_attribute('href')]
            mailto_emails = extract_emails_from_links(mailto_hrefs)
            
            all_page_emails = extracted.union(mailto_emails)

            if all_page_emails:
                for mail in all_page_emails:
                    emails_found.add((mail, page.url))
                status = 'completed'
                break  # メールが見つかった時点でこの事業所のスクレイピングを終了

            # メールが見つからず、まだ深さ上限に達していなければリンクをキューに追加
            if depth < max_depth:
                next_links = await extract_links_from_page(page, start_url)
                for link in next_links:
                    if link.split('#')[0] not in visited:
                        queue.append((link, depth + 1))

    except Exception as e:
        if not emails_found:
            status = 'failed'
    finally:
        await page.close()

    return list(emails_found), status

async def run_scraper(
    file_filter: Optional[str] = None,
    code: Optional[str] = None,
    pref: Optional[str] = None,
    city: Optional[str] = None,
    limit: Optional[int] = None,
    interval: float = 1.0,
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

    print(f"対象事業所数: {len(facilities)} 件")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        for idx, fac in enumerate(facilities, 1):
            fac_id = fac["id"]
            fac_name = fac["facility_name"]
            url = fac["url"]

            print(f"[{idx}/{len(facilities)}] Processing: ID={fac_id}, {fac_name} ({url})...")

            try:
                emails, status = await scrape_facility_emails(
                    context, url, interval=interval
                )

                if emails:
                    print(f"  -> Found {len(emails)} email(s): {[e[0] for e in emails]}")
                    db.add_emails(fac_id, emails)
                    db.update_facility_scrape_status(fac_id, 'completed')
                else:
                    print(f"  -> No email found. Status: {status}")
                    db.update_facility_scrape_status(fac_id, status)

            except Exception as e:
                print(f"  -> Error scraping {url}: {e}")
                db.update_facility_scrape_status(fac_id, 'failed')

        await browser.close()

    print("スクレイピング完了。")

def main():
    parser = argparse.ArgumentParser(description="介護事業所WebサイトからPlaywrightを用いてメールアドレスを取得します")
    parser.add_argument("-f", "--file", help="取り込みファイル識別子またはファイル名（例: 110_訪問介護）")
    parser.add_argument("--code", help="都道府県コード又は市町村コード")
    parser.add_argument("--pref", help="都道府県名（例: 北海道）")
    parser.add_argument("--city", help="市区町村名（例: 札幌市中央区）")
    parser.add_argument("-n", "--limit", type=int, help="処理件数上限")
    parser.add_argument("--interval", type=float, default=1.0, help="ページ遷移ごとの待機秒数（デフォルト: 1.0秒）")
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
        db_path=args.db,
        headless=not args.head
    ))

if __name__ == "__main__":
    main()
