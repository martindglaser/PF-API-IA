from flask import Flask, request, jsonify
from app.services import analyze_service, screenshot_service
from app.services.check_links_service import check_links
from app.services.check_images_service import check_images
from app.utils import html_cleaner
import traceback
import json

app = Flask(__name__)

SUPPORTED_LANGUAGES = {
    "es": "Spanish",
    "en": "English",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese"
}
VALID_TOLERANCE = {"low", "medium", "high"}

@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200

@app.post("/analyze")
def analyze():
    try:
        data = request.get_json(silent=True) or {}
        url = (data.get("url") or "").strip()
        tolerance = (data.get("tolerance") or "medium").lower()
        lang_code = (data.get("language") or "es").lower()

        if not url.startswith(("http://", "https://")):
            return jsonify({"Error": "Invalid or missing 'url' parameter."}), 400
        if tolerance not in VALID_TOLERANCE:
            tolerance = "medium"

        response_language = SUPPORTED_LANGUAGES.get(lang_code, "Spanish")

        import cuid
        image_cuid = cuid.cuid()
        image_filename = f"{image_cuid}.png"
        image_filename_mobile = f"{image_cuid}_mobile.png"
        # Desktop screenshot
        screenshot_path, raw_html = screenshot_service.capture_page(url, image_filename=image_filename)
        # Mobile screenshot
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
        cleaned_html = html_cleaner.clean_html(raw_html)

        links_report = check_links(url, limit=50)
        images_report = check_images(url)
        telemetry_data = {"links": links_report, "images": images_report}
        print("TELEMETRY_JSON - Errors found:")
        if links_report:
            print("Links:")
            for item in links_report:
                print(json.dumps(item, ensure_ascii=False, indent=2))
        if images_report:
            print("Images:")
            for item in images_report:
                print(json.dumps(item, ensure_ascii=False, indent=2))
        telemetry_blob = "\n<!-- TELEMETRY_JSON " + json.dumps(telemetry_data, ensure_ascii=False) + " TELEMETRY_JSON_END -->\n"

        image_paths = [screenshot_path]
        if mobile_screenshot_path:
            image_paths.append(mobile_screenshot_path)
        result = analyze_service.analyze_content(
            clean_html=cleaned_html + telemetry_blob,
            image_paths=image_paths,
            tolerance_level=tolerance,
            response_language=response_language
        )

        # Agregar el CUID y paths a la respuesta
        response = {
            "cuid": image_cuid,
            "desktop_screenshot": screenshot_path,
            "mobile_screenshot": mobile_screenshot_path
        }
        if isinstance(result, list):
            response.update({
                "whatISee": "",
                "needsModification": len(result) > 0,
                "modifications": result[:12]
            })
            return jsonify(response), 200

        response.update(result)
        return jsonify(response), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "error": "An internal error occurred in the analysis server",
            "detail": str(e)
        }), 500

@app.post("/check-links")
def check_links_endpoint():
    try:
        data = request.get_json(silent=True) or {}
        url = (data.get("url") or "").strip()
        limit = int(data.get("limit") or 80)
        if not url.startswith(("http://", "https://")):
            return jsonify({"error": "Invalid or missing 'url' parameter."}), 400
        result = check_links(url, limit=limit)
        return jsonify(result), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "check-links failed", "detail": str(e)}), 500

@app.post("/check-images")
def check_images_endpoint():
    try:
        data = request.get_json(silent=True) or {}
        url = (data.get("url") or "").strip()
        if not url.startswith(("http://", "https://")):
            return jsonify({"error": "Invalid or missing 'url' parameter."}), 400
        result = check_images(url)
        return jsonify(result), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "check-images failed", "detail": str(e)}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001)

