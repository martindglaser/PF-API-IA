
from playwright.sync_api import sync_playwright

IGNORE_DOMAINS = ("pixel.wp.com", "google-analytics.com")

def check_images(target_url: str) -> dict:
    """
    Devuelve JSON con:
    {
      "url": "...",
      "imagesTotal": n,
      "broken": [{ "src": "..."}],
      "missingAlt": [{ "src": "..."}]
    }
    """
    out = {
        "url": target_url,
        "imagesTotal": 0,
        "broken": [],
        "missingAlt": []
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(target_url, wait_until="domcontentloaded", timeout=60000)

        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass  

        imgs = page.eval_on_selector_all(
            "img",
            """els => els.map(e => ({
                src: e.currentSrc || e.src || "",
                alt: e.getAttribute('alt'),
                naturalWidth: e.naturalWidth,
                naturalHeight: e.naturalHeight
            }))"""
        )

        out["imagesTotal"] = len(imgs)

        for im in imgs:
            src = (im.get("src") or "").strip()
            nw = im.get("naturalWidth", 0) or 0
            nh = im.get("naturalHeight", 0) or 0

       
            if any(d in src for d in IGNORE_DOMAINS):
                continue

            
            if nw == 1 and nh == 1:
                continue

          
            if not im.get("alt"):
                out["missingAlt"].append({"src": src})

       
            if nw == 0 or nh == 0:
                out["broken"].append({"src": src})

        browser.close()

    return out
