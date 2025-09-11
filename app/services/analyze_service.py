import os
import time
import random
import json
import google.generativeai as genai
from PIL import Image
from dotenv import load_dotenv
from app.utils.api_helpers import is_429, extract_retry_delay

# Load API Key from .env file
load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def analyze_content(clean_html: str, image_path: str, tolerance_level: str, response_language: str = "en") -> dict:
    """
    Sends the content and image to Gemini AI for visual analysis.
    Handles retries in case of quota errors.
    """
    model = genai.GenerativeModel("gemini-1.5-flash") # Use latest model

    Tolerance = {
        "high": "Only critical errors that prevent using the page or make it unreadable (e.g., overlapping buttons, covered text).",
        "medium": "Visible errors that affect the experience, even if not blocking (e.g., misaligned elements, crowded text).",
        "low": "Minor or aesthetic details that could be improved (e.g., uneven margins, unharmonious colors)."
    }

    prompt = f"""
    You are a visual interface checker. Return ONLY valid JSON.

    Required fields:
    - "whatISee": string (brief description of what is seen on the website)
    - "needsModification": boolean
    - "modifications": array of strings, each item a concrete correction.

    Criteria: detect only real visual problems (overlapping text, misaligned buttons, cropping, etc.).
    Tolerance: {tolerance_level} ({Tolerance.get(tolerance_level, "medium")}).

    IMPORTANT:
    - If there are no problems, "needsModification": false and "modifications": [].
    - Do not add any text outside the JSON.

    Below is the IMAGE (screenshot) and an extract of the plain HTML.
    HTML:
    {clean_html}

    Please provide your response in {response_language}.
    """

    MAX_RETRIES = 6
    attempt = 0

    while True:
        try:
            print("Querying the AI model...")
            parts = [
                prompt,
                Image.open(image_path),
            ]
            resp = model.generate_content(parts, generation_config={
                "response_mime_type": "application/json"
            })
            return json.loads(resp.text)

        except Exception as e:
            attempt += 1
            if is_429(e) and attempt <= MAX_RETRIES:
                delay = extract_retry_delay(e, fallback=60)
                delay = max(delay, 2 ** attempt) + random.uniform(1, 3)
                print(f"Quota error (429). Retrying in {int(delay)}s (attempt {attempt}/{MAX_RETRIES})...")
                time.sleep(delay)
                continue
            else:
                print(f"Unexpected error contacting AI: {e}")
                raise