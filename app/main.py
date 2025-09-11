from flask import Flask, request, jsonify
from app.services import analyze_service, screenshot_service
from app.utils import html_cleaner

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
        print(f"1. Starting capture for URL: {url}")
        screenshot_path, html_content = screenshot_service.capture_page(url)

        print("2. Cleaning HTML...")
        cleaned_html_text = html_cleaner.clean_html(html_content)

        print("3. Sending to AI for analysis...")
        analysis_result = analyze_service.analyze_content(
            clean_html=cleaned_html_text,
            image_path=screenshot_path,
            tolerance_level=tolerance,
            response_language=language_name
        )

        print("4. Analysis completed. Returning result.")
        return jsonify(analysis_result)

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        print(f"Unexpected server error: {e}")
        return jsonify({"error": "An internal error occurred in the analysis server"}), 500

@app.route('/languages', methods=['GET'])
def get_supported_languages():
    """
    Returns a list of supported languages for the analysis response.
    """
    return jsonify({"supported_languages": SUPPORTED_LANGUAGES})

if __name__ == '__main__':
    app.run(debug=True, port=5001)