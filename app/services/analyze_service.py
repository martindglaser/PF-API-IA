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

def analyze_content(clean_html: str, image_paths: list, tolerance_level: str, response_language: str = "en") -> dict:
    """
    Sends the content and image to Gemini AI for visual analysis.
    Handles retries in case of quota errors.
    """
    model = genai.GenerativeModel("gemini-2.5-flash") # Use latest model

    Tolerance = {
        "high": "Only critical errors that prevent using the page or make it unreadable (e.g., overlapping buttons, covered text).",
        "low": "Minor or aesthetic details that could be improved (e.g., uneven margins, unharmonious colors)."
    }

    prompt = f"""
    You are a visual interface checker. Return ONLY valid JSON.

    Required fields:
    - "whatISee": string (brief description of what is seen on the website)
    - "needsModification": boolean
    - "modifications": (
        - errorDescription: a description of the detected problem and the line number in the source code where the error occurred,
        - codeSuggestion: an object with three attributes: HTML, CSS, and JS, containing suggested code modifications to fix the problem. This attribute should only display the code itself, without any explanation.
    )

    Criteria: (
        UI/Styles: Misaligned buttons, inconsistent font styles or colors, overlapping elements.
        Forms: No validation of required fields, allowing submission of invalid data.
        Buttons/Actions: Buttons with no feedback after clicking, duplicate or blocking events.
        Images/Resources: Unoptimized, large image files, no lazy loading, broken images.
        Text: Empty list without a "no data" message, truncated text on screen.
        Accessibility: Images without alt attributes, low contrast, not keyboard accessible.
        Links: Broken links (404 error) or incorrect redirects, caching issues due to lack of versioning.
        Web Responsiveness: Not optimized for mobile/tablet devices, unnecessary horizontal scrolling.
    )
    
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

    MAX_PIXELS = 89478484
    MAX_DIMENSION = 16383
    while True:
        try:
            print("Querying the AI model...")
            parts = [prompt]
            for img_path in image_paths:
                try:
                    img = Image.open(img_path)
                    orig_width, orig_height = img.width, img.height
                    # Calcular el factor de escala más restrictivo
                    scale_dim = min(MAX_DIMENSION / img.width, MAX_DIMENSION / img.height, 1.0)
                    scale_pix = min((MAX_PIXELS / (img.width * img.height)) ** 0.5, 1.0)
                    scale = min(scale_dim, scale_pix)
                    if scale < 1.0:
                        new_width = int(img.width * scale)
                        new_height = int(img.height * scale)
                        print(f"Resizing image {img_path} from {orig_width}x{orig_height} to {new_width}x{new_height}")
                        img = img.resize((new_width, new_height), Image.LANCZOS)
                    parts.append(img)
                except Exception as e:
                    print(f"Could not open image {img_path}: {e}")
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