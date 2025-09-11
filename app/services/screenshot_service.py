from playwright.sync_api import sync_playwright, Error

def capture_page(url: str) -> tuple[str, str]:
    """
    Navigates to a URL, takes a screenshot, and returns the HTML content.
    Returns a tuple (screenshot_path, html_content).
    Raises an exception if the URL is invalid or cannot be accessed.
    """
    screenshot_path = "page.png"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000) # 60s timeout
            page.screenshot(path=screenshot_path, full_page=True)
            html_content = page.content()
        except Error as e:
            browser.close()
            raise ValueError(f"Could not access or process the URL: {url}. Error: {e}")

        browser.close()
    return screenshot_path, html_content