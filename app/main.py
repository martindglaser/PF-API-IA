from flask import Flask, request, jsonify
from flask_cors import CORS
from app.services import analyze_service, screenshot_service
from app.services.check_links_service import check_links
from app.services.check_images_service import check_images
from app.utils import html_cleaner
import traceback
import json
import sys  
import os


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:5001")
ASSETS_ROOT_INSIDE_CONTAINER = "/assets"
SCREENSHOT_DIR_INSIDE_CONTAINER = f"{ASSETS_ROOT_INSIDE_CONTAINER}/screenshots"

app = Flask(__name__, static_folder=ASSETS_ROOT_INSIDE_CONTAINER, static_url_path='/assets')
CORS(app)


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

        raw_categories = data.get("categories") if data.get("categories") is not None else (data.get("data") or {}).get("categories")
        if isinstance(raw_categories, list):
            categories = [str(c) for c in raw_categories]
        else:
            categories = []

        if not url.startswith(("http://", "https://")):
            return jsonify({"Error": "Invalid or missing 'url' parameter."}), 400
        if tolerance not in VALID_TOLERANCE:
            tolerance = "medium"

        response_language = SUPPORTED_LANGUAGES.get(lang_code, "Spanish")

        import cuid
        image_cuid = cuid.cuid()
        image_filename = f"{image_cuid}.png"
        image_filename_mobile = f"{image_cuid}_mobile.png"
   
        desktop_save_path = f"{SCREENSHOT_DIR_INSIDE_CONTAINER}/{image_filename}"
        mobile_save_path = f"{SCREENSHOT_DIR_INSIDE_CONTAINER}/{image_filename_mobile}"
        
       
        screenshot_path, raw_html = screenshot_service.capture_page(url, save_path=desktop_save_path)
      
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            iphone_12 = p.devices["iPhone 12"]
            page = browser.new_page(**iphone_12)
            try:
                
                page.goto(url, wait_until="networkidle", timeout=60000)
             
                import time
           
                scroll_height = page.evaluate("() => document.body.scrollHeight")
                current = 0
                step = 500
                while current < scroll_height:
                    page.evaluate(f"window.scrollTo(0, {current})")
                    time.sleep(0.3)
                    current += step
                    scroll_height = page.evaluate("() => document.body.scrollHeight")
          
                time.sleep(2)
                page.screenshot(path=mobile_save_path, full_page=True)
            except Exception as e:
                browser.close()
                print(f"Mobile screenshot failed: {e}")
                mobile_save_path = None
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
       
        telemetry_blob = "\n\n"

        image_path = [screenshot_path]
        if mobile_save_path:
            image_path.append(mobile_save_path)
            
        result = analyze_service.analyze_content(
            clean_html=cleaned_html + telemetry_blob,
            image_paths=image_path,
            tolerance_level=tolerance,
            response_language=response_language,
            categories=categories
        )

        desktop_url_path = f"/assets/screenshots/{image_filename}"
        mobile_url_path = f"/assets/screenshots/{image_filename_mobile}" if mobile_save_path else None

        response = {
            "cuid": image_cuid,
            "desktop_screenshot": f"{API_BASE_URL}{desktop_url_path}",
            "mobile_screenshot": f"{API_BASE_URL}{mobile_url_path}" if mobile_url_path else None
        }

        if categories:
            response["categories"] = categories
        
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
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    app.run(debug=True, host='0.0.0.0', port=port)