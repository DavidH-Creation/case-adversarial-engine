#!/usr/bin/env python3
"""
Scraper for 人民法院案例库 (rmfyalk.court.gov.cn).

The site requires OAuth login. This script:
1. Opens a Playwright browser for you to log in manually
2. After login, calls the search API with your authenticated session
3. Paginates through all cases and saves to data/court_cases_index.json

Usage:
    pip install playwright
    playwright install chromium
    python scripts/scrape_court_cases.py

Options:
    --page-size N      Results per page (default: 15, max ~50)
    --start-page N     Resume from page N (default: 1)
    --delay SECONDS    Delay between requests (default: 1.5)
    --output PATH      Output file (default: data/court_cases_index.json)
    --cookie-file PATH Load cookies from a JSON file instead of manual login
    --save-cookies PATH  Save cookies after login for reuse
"""

import argparse
import asyncio
import json
import random
import sys
import time
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("=" * 60)
    print("Playwright is not installed. Install it with:")
    print("  pip install playwright")
    print("  playwright install chromium")
    print("=" * 60)
    sys.exit(1)

BASE_URL = "https://rmfyalk.court.gov.cn"
SEARCH_API = f"{BASE_URL}/cpws_al_api/api/cpwsAl/search"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "court_cases_index.json"


def build_search_payload(page: int, size: int) -> dict:
    """Build the POST body for the search API."""
    return {
        "page": page,
        "size": size,
        "lib": "qb",
        "searchParams": {
            "userSearchType": 1,
            "isAdvSearch": "0",
            "selectValue": "qw",
            "lib": "cpwsAl_qb",
            "sort_field": "",
        },
    }


def strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    import re

    return re.sub(r"<[^>]*>", "", text).strip()


def extract_keywords(title: str, cause: str) -> list[str]:
    """Extract keywords from title and cause of action."""
    import re

    keywords = []
    if cause:
        keywords.append(cause)
    patterns = (
        r"(合同纠纷|侵权|借贷|离婚|继承|劳动争议|买卖|租赁|担保|保险|"
        r"知识产权|著作权|商标|专利|公司|股权|破产|行政|刑事|民事|"
        r"交通事故|医疗|建设工程|物权|债权|不当得利|"
        r"强奸|盗窃|诈骗|故意伤害|抢劫|贪污|受贿|非法经营|"
        r"走私|毒品|虚假诉讼|滥用职权|玩忽职守)"
    )
    for m in re.finditer(patterns, title):
        if m.group() not in keywords:
            keywords.append(m.group())
    return keywords


def normalize_case(raw: dict) -> dict | None:
    """Map a raw API response item to our index schema.

    API field mapping (discovered from rmfyalk.court.gov.cn):
      cpws_al_ajzh      → case_number  (案号)
      cpws_al_slfy_name  → court       (审理法院)
      cpws_al_sort_name  → cause       (案由)
      cpws_al_cpyz       → summary     (裁判要旨, contains HTML)
      cpws_al_title      → title
      cpws_al_id / id    → case ID for URL
      cpws_al_zs_date    → date
      cpws_al_no         → reference number (编号)
      cpws_al_type       → 01=指导性案例, 02=参考案例
      cpws_al_case_sort_name → category (刑事/民事/行政/...)
    Response structure: {code: 0, data: {totalCount: N, datas: [...]}}
    """
    case_number = raw.get("cpws_al_ajzh", "")
    court = raw.get("cpws_al_slfy_name", "")
    cause = raw.get("cpws_al_sort_name", "")
    title = raw.get("cpws_al_title", "")

    summary = strip_html(raw.get("cpws_al_cpyz", "")) or title
    if len(summary) > 500:
        summary = summary[:497] + "..."

    case_id = raw.get("cpws_al_id") or raw.get("id") or ""
    url = f"{BASE_URL}/ws/detail/{case_id}" if case_id else ""

    keywords = extract_keywords(title + " " + summary, cause)

    if not case_number and not title:
        return None

    return {
        "case_number": case_number,
        "court": court,
        "cause_of_action": cause,
        "keywords": keywords,
        "summary": summary,
        "url": url,
    }


async def wait_for_login(page) -> bool:
    """Navigate to login and wait for the user to complete authentication."""
    print("\n" + "=" * 60)
    print("Please log in to 人民法院案例库 in the browser window.")
    print("The script will continue automatically after login.")
    print("=" * 60 + "\n")

    # Navigate to a page that requires auth - it will redirect to login
    await page.goto(f"{BASE_URL}/view/list.html", wait_until="networkidle", timeout=30000)

    # Wait for redirect back to rmfyalk after successful login
    # or wait for the user to navigate there manually
    for _ in range(600):  # 10 minute timeout
        current_url = page.url
        if "rmfyalk.court.gov.cn" in current_url and "account.court.gov.cn" not in current_url:
            # Verify we're actually authenticated
            resp = await page.evaluate("""
                async () => {
                    try {
                        const r = await fetch('/cpws_al_api/api/cpwsAl/search', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({
                                page: 1, size: 1, lib: 'qb',
                                searchParams: {
                                    userSearchType: 1, isAdvSearch: '0',
                                    selectValue: 'qw', lib: 'cpwsAl_qb', sort_field: ''
                                }
                            })
                        });
                        const data = await r.json();
                        return data;
                    } catch(e) {
                        return {code: -1, msg: e.message};
                    }
                }
            """)
            if resp.get("code") != 401:
                print("Login successful! Starting scrape...")
                return True
        await asyncio.sleep(1)

    print("Login timeout (10 minutes). Exiting.")
    return False


async def fetch_page(page, page_num: int, page_size: int) -> dict:
    """Fetch a single page of search results using the browser's authenticated session."""
    payload = build_search_payload(page_num, page_size)
    result = await page.evaluate(
        """
        async (payload) => {
            const r = await fetch('/cpws_al_api/api/cpwsAl/search', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            return await r.json();
        }
    """,
        payload,
    )
    return result


async def discover_response_format(page, page_size: int) -> None:
    """Fetch one page and print the response structure to help debug field mapping."""
    result = await fetch_page(page, 1, page_size)
    print("\n--- API Response Structure ---")
    print(f"Top-level keys: {list(result.keys())}")

    # Try to find the data list
    data_list = None
    for key in ["data", "result", "rows", "list", "records", "content"]:
        if key in result and isinstance(result[key], (list, dict)):
            data_list = result[key]
            print(f"Data found in key: '{key}'")
            break

    if data_list is None and isinstance(result.get("data"), dict):
        for key in ["list", "rows", "records", "content", "result"]:
            if key in result["data"] and isinstance(result["data"][key], list):
                data_list = result["data"][key]
                print(f"Data found in key: 'data.{key}'")
                break

    if data_list and isinstance(data_list, list) and len(data_list) > 0:
        sample = data_list[0]
        print(f"Sample record keys: {list(sample.keys())}")
        print(f"Sample record: {json.dumps(sample, ensure_ascii=False, indent=2)[:2000]}")
    else:
        print(f"Full response: {json.dumps(result, ensure_ascii=False, indent=2)[:3000]}")
    print("--- End Response Structure ---\n")


def extract_data_list(result: dict) -> tuple[list[dict], int]:
    """Extract the list of cases and total count from API response.

    Actual response format: {code: 0, msg: "ok", data: {totalCount: N, datas: [...]}}
    """
    if isinstance(result.get("data"), dict):
        data = result["data"]
        total = data.get("totalCount", 0) or data.get("total", 0)
        items = data.get("datas") or data.get("list") or data.get("rows") or []
        return items, total

    return [], 0


async def scrape_all(args) -> None:
    """Main scraping loop."""
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing data if resuming
    existing_cases = []
    seen_ids = set()
    if output_path.exists() and args.start_page > 1:
        with open(output_path, "r", encoding="utf-8") as f:
            existing_cases = json.load(f)
        seen_ids = {c.get("case_number", "") for c in existing_cases}
        print(f"Loaded {len(existing_cases)} existing cases from {output_path}")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )

        # Load cookies if provided
        if args.cookie_file and Path(args.cookie_file).exists():
            with open(args.cookie_file, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
            print(f"Loaded cookies from {args.cookie_file}")

        page = await context.new_page()

        # Login or verify session
        if args.cookie_file and Path(args.cookie_file).exists():
            await page.goto(f"{BASE_URL}/view/list.html", wait_until="networkidle", timeout=30000)
            # Verify auth
            test = await fetch_page(page, 1, 1)
            if test.get("code") == 401:
                print("Cookies expired. Please log in manually.")
                if not await wait_for_login(page):
                    return
        else:
            if not await wait_for_login(page):
                return

        # Save cookies for reuse
        if args.save_cookies:
            cookies = await context.cookies()
            with open(args.save_cookies, "w", encoding="utf-8") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            print(f"Cookies saved to {args.save_cookies}")

        # Discover response format
        await discover_response_format(page, args.page_size)

        # Fetch first page to get total count
        first_result = await fetch_page(page, 1, args.page_size)
        data_list, total = extract_data_list(first_result)

        if total == 0 and len(data_list) > 0:
            # Estimate total from homepage (5363 as seen)
            total = 5363
            print(f"Could not determine total from API, using estimate: {total}")
        else:
            print(f"Total cases: {total}")

        total_pages = (total + args.page_size - 1) // args.page_size
        print(f"Total pages: {total_pages} (page size: {args.page_size})")

        all_cases = list(existing_cases)
        errors = 0
        max_errors = 10

        for page_num in range(args.start_page, total_pages + 1):
            try:
                if page_num == 1 and args.start_page == 1:
                    # Already fetched first page
                    items = data_list
                else:
                    result = await fetch_page(page, page_num, args.page_size)

                    if result.get("code") == 401:
                        print(f"\nSession expired at page {page_num}. Saving progress...")
                        break

                    items, _ = extract_data_list(result)

                if not items:
                    print(f"\nNo data on page {page_num}. Might be the last page.")
                    if page_num > 1:
                        break
                    continue

                new_count = 0
                for item in items:
                    case = normalize_case(item)
                    if case and case["case_number"] not in seen_ids:
                        all_cases.append(case)
                        seen_ids.add(case["case_number"])
                        new_count += 1

                progress = min(100, page_num * 100 // total_pages)
                print(
                    f"  Page {page_num}/{total_pages} "
                    f"({progress}%) - {len(items)} items, {new_count} new "
                    f"[Total: {len(all_cases)}]",
                    end="\r",
                )

                # Save periodically (every 10 pages)
                if page_num % 10 == 0:
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(all_cases, f, ensure_ascii=False, indent=2)

                errors = 0  # Reset error counter on success

                # Random delay to be polite
                delay = args.delay + random.uniform(0, args.delay * 0.5)
                await asyncio.sleep(delay)

            except Exception as e:
                errors += 1
                print(f"\nError on page {page_num}: {e}")
                if errors >= max_errors:
                    print(f"Too many consecutive errors ({max_errors}). Stopping.")
                    break
                # Longer delay on error
                await asyncio.sleep(args.delay * 3)

        # Final save
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_cases, f, ensure_ascii=False, indent=2)
        print(f"\n\nDone! Saved {len(all_cases)} cases to {output_path}")

        await browser.close()


def main():
    parser = argparse.ArgumentParser(description="Scrape 人民法院案例库")
    parser.add_argument("--page-size", type=int, default=15, help="Results per page")
    parser.add_argument("--start-page", type=int, default=1, help="Start from page N")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay between requests (sec)")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT), help="Output JSON path")
    parser.add_argument("--cookie-file", type=str, help="Load cookies from JSON file")
    parser.add_argument("--save-cookies", type=str, help="Save cookies to JSON file after login")
    args = parser.parse_args()
    asyncio.run(scrape_all(args))


if __name__ == "__main__":
    main()
