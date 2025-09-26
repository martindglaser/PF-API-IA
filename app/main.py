from flask import Flask, request, jsonify
from app.services import analyze_service, screenshot_service
from app.utils import html_cleaner
import cuid

app = Flask(__name__)

# Supported languages with explicit names for AI
SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese"
}

@app.route('/analyze', methods=['POST'])
def analyze_url():
    """
    Endpoint to analyze a URL.
    Receives a JSON with "url", "tolerance", and optional "language".
    Returns the analysis in JSON format.
    """
    data = request.get_json()
    if not data or 'url' not in data:
        return jsonify({"error": "URL is required"}), 400

    url = data['url']
    tolerance = data.get('tolerance', 'medium').lower()
    if tolerance not in ['high', 'medium', 'low']:
        return jsonify({"error": "Tolerance must be 'high', 'medium', or 'low'"}), 400

    # Language is optional, default is 'en'
    language_code = data.get('language', 'en').lower()
    if language_code not in SUPPORTED_LANGUAGES:
        return jsonify({
            "error": f"Invalid language '{language_code}'. Supported languages are:",
            "supported_languages": SUPPORTED_LANGUAGES
        }), 400

    # Use explicit language name for AI prompt
    language_name = SUPPORTED_LANGUAGES[language_code]

    try:
        # 1. Generate a CUID and set as image name
        image_cuid = cuid.cuid()
        image_filename = f"{image_cuid}.png"
        print(f"1. Starting capture for URL: {url} with image name: {image_filename}")
        import time
        screenshot_path, html_content = None, None
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                import time
                time.sleep(7)  # Esperar 7 segundos para que carguen imágenes y recursos
                page.screenshot(path=f"../assets/screenshots/{image_filename}", full_page=True)
                html_content = page.content()
                screenshot_path = f"../assets/screenshots/{image_filename}"
            except Exception as e:
                browser.close()
                print(f"Desktop screenshot failed: {e}")
                screenshot_path = None
            browser.close()

        # Mobile capture
        image_filename_mobile = f"{image_cuid}_mobile.png"
        print(f"1b. Starting mobile capture for URL: {url} with image name: {image_filename_mobile}")
        from playwright.sync_api import sync_playwright
        mobile_screenshot_path = f"../assets/screenshots/{image_filename_mobile}"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            iphone_12 = p.devices["iPhone 12"]
            page = browser.new_page(**iphone_12)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                # Scroll incremental para forzar carga de imágenes lazy-load
                import time
                scroll_height = page.evaluate("() => document.body.scrollHeight")
                current = 0
                step = 500
                while current < scroll_height:
                    page.evaluate(f"window.scrollTo(0, {current})")
                    time.sleep(0.3)
                    current += step
                    scroll_height = page.evaluate("() => document.body.scrollHeight")
                # Esperar un poco al final
                time.sleep(2)
                page.screenshot(path=mobile_screenshot_path, full_page=True)
            except Exception as e:
                browser.close()
                print(f"Mobile screenshot failed: {e}")
                mobile_screenshot_path = None
            browser.close()

        print("2. Cleaning HTML...")
        cleaned_html_text = html_cleaner.clean_html(html_content)

        print("3. Sending to AI for analysis (desktop + mobile)...")
        image_paths = [screenshot_path]
        if mobile_screenshot_path:
            image_paths.append(mobile_screenshot_path)
        analysis_result = analyze_service.analyze_content(
            clean_html=cleaned_html_text,
            image_paths=image_paths,
            tolerance_level=tolerance,
            response_language=language_name
        )

        print("4. Analysis completed. Returning result.")
        # Agregar el CUID y paths a la respuesta
        response = {
            'cuid': image_cuid,
            'desktop_screenshot': screenshot_path,
            'mobile_screenshot': mobile_screenshot_path,
            'analysis': analysis_result
        }
        return jsonify(response)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print(f"Unexpected server error: {e}")
        return jsonify({"error": "An internal error occurred in the analysis server"}), 500