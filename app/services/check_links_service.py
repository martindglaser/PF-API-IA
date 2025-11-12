
from playwright.sync_api import sync_playwright
import re

def _abs(base_url: str, href: str) -> str:
    if not href:
        return ""
    if href.startswith("http"):
        return href
    host = re.match(r"^https?://[^/]+", base_url)
    if not host:
        return href
    if href.startswith("/"):
        return f"{host.group(0)}{href}"
    return f"{base_url.rstrip('/')}/{href}"

def check_links(target_url: str, limit: int = 80) -> dict:
    """
    Devuelve JSON con:
    {
      "url": "...",
      "totalLinks": n,
      "checked": n2,
      "broken": [{ "url": "...", "status": 404 }, ...],
      "suspicious": [{ "url": "javascript:void(0)" }, {"url":"#"}]
    }
    """
    data = {
        "url": target_url,
        "totalLinks": 0,
        "checked": 0,
        "broken": [],
        "suspicious": []
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = p.request.new_context(ignore_https_errors=True)
        page = browser.new_page()
        
       
        page.goto(target_url, wait_until="networkidle", timeout=60000)

        raw_hrefs = page.eval_on_selector_all("a", "els => els.map(e => e.getAttribute('href'))")
        hrefs = [h for h in raw_hrefs if h]
        data["totalLinks"] = len(hrefs)

        suspicious = []
        candidates = []
        for h in hrefs:
            if h in ("#",) or h.lower().startswith("javascript:void"):
                suspicious.append({"url": h})
            else:
                candidates.append(_abs(page.url, h))

        data["suspicious"] = suspicious

        broken = []
        for u in candidates[:limit]:
            try:
                
                r = ctx.fetch(u, method="HEAD", max_redirects=5, timeout=15000)
                status = r.status
                if status == 405 or status == 501:
                    r = ctx.fetch(u, method="GET", max_redirects=5, timeout=15000)
                    status = r.status
                if status >= 400:
                    broken.append({"url": u, "status": status})
            except Exception as e:
                broken.append({"url": u, "error": str(e)})

        data["broken"] = broken
        data["checked"] = min(len(candidates), limit)

        browser.close()
        ctx.dispose()

    return data
