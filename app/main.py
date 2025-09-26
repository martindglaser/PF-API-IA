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
            return jsonify({"error": "Parámetro 'url' inválido o ausente."}), 400
        if tolerance not in VALID_TOLERANCE:
            tolerance = "medium"

        response_language = SUPPORTED_LANGUAGES.get(lang_code, "Spanish")

        screenshot_path, raw_html = screenshot_service.capture_page(url)
        cleaned_html = html_cleaner.clean_html(raw_html)

        links_report = check_links(url, limit=50)
        images_report = check_images(url)
        telemetry_blob = "\n<!-- TELEMETRY_JSON " + json.dumps({"links": links_report, "images": images_report}, ensure_ascii=False) + " TELEMETRY_JSON_END -->\n"

        result = analyze_service.analyze_content(
            clean_html=cleaned_html + telemetry_blob,
            image_path=screenshot_path,
            tolerance_level=tolerance,
            response_language=response_language
        )

        if isinstance(result, list):
            return jsonify({
                "whatISee": "",
                "needsModification": len(result) > 0,
                "modifications": result[:12]
            }), 200

        return jsonify(result), 200

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
            return jsonify({"error": "Parámetro 'url' inválido o ausente."}), 400
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
            return jsonify({"error": "Parámetro 'url' inválido o ausente."}), 400
        result = check_images(url)
        return jsonify(result), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": "check-images failed", "detail": str(e)}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001)

