# crawl_hotchkiss.py
# Crawl every URL in hotchkiss_urls.txt and store:
#   url | title | markdown | crawled_at
# in hotchkiss_content.db. Uses ONE Playwright context
# with cf_cookies.json so Cloudflare never re‑challenges.

import asyncio, sqlite3, time, pathlib
from bs4 import BeautifulSoup
from markdownify import markdownify as md          # Markdown converter
from playwright.async_api import async_playwright

# ───────── helper: extract main article HTML ─────────
def main_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Remove elements by class name
    for cls in ["fsNavigation"]:
        for tag in soup.select(f".{cls}"):
            tag.decompose()

    # Try to locate main content
    main = soup.find("main", id="fsPageContent") or soup.find("div", id="fsPageContent")
    if main:
        return "".join(str(c) for c in main.contents)

    # Fallback to body
    body = soup.body
    return "".join(str(c) for c in body.contents) if body else html
# ─────────────────────────────────────────────────────

# paths & settings
PRJ        = pathlib.Path(__file__).resolve().parent
URL_FILE   = PRJ / "hotchkiss_urls.txt"
DB_FILE    = PRJ / "hotchkiss_content.db"
COOKIE     = PRJ / "cf_cookies.json"
DELAY_SECS = 1.0

# read URL list
def read_urls(p: pathlib.Path) -> list[str]:
    return [u.strip() for u in p.read_text().splitlines() if u.strip()]

# ensure 4‑column schema
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pages(
          url        TEXT PRIMARY KEY,
          title      TEXT,
          markdown   TEXT,
          crawled_at INTEGER
        );
        """
    )
    return conn

# main async crawl
async def crawl_all(url_list: list[str]):
    conn = db()
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx     = await browser.new_context(storage_state=str(COOKIE))
        page    = await ctx.new_page()

        for url in url_list:
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                full_html = await page.content()
                soup      = BeautifulSoup(full_html, "html.parser")
                title     = soup.title.get_text(" ", strip=True) if soup.title else ""

                html_content = main_html(full_html)

                # Rewrite asset URLs and handle media
                soup = BeautifulSoup(html_content, "html.parser")

                # Fix image paths
                for img in soup.find_all("img"):
                    src = img.get("src", "")
                    if src.startswith("/"):
                        img["src"] = f"https://hotchkiss.org{src}"

                # Replace <video src="blob:..."> with placeholder text
                for video in soup.find_all("video"):
                    src = video.get("src", "")
                    if src.startswith("blob:"):
                        placeholder = soup.new_tag("p")
                        placeholder.string = "[Embedded video: not directly extractable]"
                        video.replace_with(placeholder)

                # Convert iframe embeds to Markdown links
                for iframe in soup.find_all("iframe"):
                    src = iframe.get("src", "")
                    if "vimeo.com" in src or "youtube.com" in src:
                        link = soup.new_tag("p")
                        link.string = f"[Watch video]({src})"
                        iframe.replace_with(link)

                # Convert to markdown
                markdown = md(str(soup), heading_style="ATX")

                # Format date as MMDDYYYY
                crawled_at = time.strftime("%m%d%Y", time.localtime())

                conn.execute(
                    "INSERT OR REPLACE INTO pages (url, title, markdown, crawled_at) "
                    "VALUES (?,?,?,?)",
                    (url, title, markdown, crawled_at)
                )

                print("✓", url)
                await asyncio.sleep(DELAY_SECS)

            except Exception as e:
                print("❌", url, e)

        await ctx.close(); await browser.close()
        conn.commit(); conn.close()

# entry point
if __name__ == "__main__":
    urls = read_urls(URL_FILE)
    print(f"🕷️  Crawling {len(urls)} pages with one verified session …")
    asyncio.run(crawl_all(urls))
    print("✅  Done")