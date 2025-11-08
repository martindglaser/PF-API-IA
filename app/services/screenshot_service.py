from playwright.sync_api import sync_playwright, Error


def capture_page(url: str, save_path: str) -> tuple[str, str]:
    """
    Navega a una URL, toma una captura de pantalla y devuelve el contenido HTML.
    Guarda la captura en el 'save_path' proporcionado.
    Devuelve una tupla (screenshot_path, html_content).
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000) 
            
 
            page.screenshot(path=save_path, full_page=True)
            html_content = page.content()
        except Error as e:
            browser.close()
            raise ValueError(f"Could not access or process the URL: {url}. Error: {e}")

        browser.close()
    
  
    return save_path, html_content