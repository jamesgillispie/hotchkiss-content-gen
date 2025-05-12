# harvest_urls.py  ── run this first

import requests, re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

ROOT         = "https://www.hotchkiss.org"
HTML_SITEMAP = f"{ROOT}/site-map"
SKIP_SUFFIX  = re.compile(r"\.(pdf|png|jpe?g|gif|svg)$", re.I)
DOMAIN_RE    = re.compile(r"^https?://(?:www\.)?hotchkiss\.org", re.I)

def get_urls():
    html  = requests.get(HTML_SITEMAP, timeout=10).text
    soup  = BeautifulSoup(html, "html.parser")
    urls  = {
        urljoin(ROOT, a["href"].strip())
        for a in soup.select("a[href]")
        if DOMAIN_RE.match(urljoin(ROOT, a["href"]))
           and not SKIP_SUFFIX.search(a["href"])
    }
    return sorted(urls)

if __name__ == "__main__":
    urls = get_urls()
    print(f"➡️  {len(urls)} crawlable pages harvested")
    with open("hotchkiss_urls.txt", "w") as f:
        f.write("\n".join(urls))