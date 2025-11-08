import os
import re
import json
import time
import random
from typing import Dict, Any


from dotenv import load_dotenv
from PIL import Image
import google.generativeai as genai


load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


MODEL_ID = os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash-lite")
model = genai.GenerativeModel(MODEL_ID)


def _coerce_json(txt: str):
    s = (txt or "").strip()
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s)
    s = re.sub(r"```(?:json)?", "", s, flags=re.IGNORECASE).replace("```", "")
    starts = [i for i in (s.find("{"), s.find("[")) if i != -1]
    if not starts:
        return {"whatISee": "", "needsModification": False, "modifications": []}
    start = min(starts)
    end = max(s.rfind("}"), s.rfind("]"))
    if end == -1 or end < start:
        return {"whatISee": "", "needsModification": False, "modifications": []}
    try:
        return json.loads(s[start:end + 1])
    except Exception:
        return {"whatISee": "", "needsModification": False, "modifications": []}


def analyze_content(
    clean_html: str,
    image_paths: list,
    tolerance_level: str,
    response_language: str = "Spanish"
) -> Dict[str, Any]:
    prompt = f"""
You are a Front-End error detector.


FIRST: review the complete HTML provided to you (the second element of the input).
If you detect that the page is BLOCKING access due to anti-bot measures—specifically clear signals such as: "captcha", "recaptcha", "verify you are human", "please complete the security check", "are you human", "cf-chl-bypass", "cloudflare-challenge"—you MUST return ONLY this valid JSON and NOTHING ELSE:


{{"whatISee":"Page blocked by anti-bot: <brief reason in {response_language}>", "needsModification": false, "modifications": []}}


The reason must be brief (1–6 words) and in {response_language} (e.g., "captcha present", "Cloudflare verification").
If you do NOT detect anti-bot blocking, proceed with the normal analysis described below.


Return ONLY valid JSON. If there are no defects, respond: {{ "whatISee":"", "needsModification": false, "modifications": [] }}.
If the HTML includes <!-- TELEMETRY_JSON … TELEMETRY_JSON_END --> use it as objective evidence (broken links/images) and prioritize the defects confirmed in that block: include them in "modifications" even if they are not evident in the images.


Strict output:
- JSON object with: "whatISee": string, "needsModification": boolean, "modifications": array.
- Each item in "modifications" must include ONLY:
  - category (UI/Styles, Forms, Buttons, Images, Texts, Accessibility, Links, Responsiveness)
  - description (brief, 10–80 characters)
  - severity (Critical, Medium, Low)
  - state (confirmed or inconclusive)
  - selector_css


Criteria:
1) UI/Styles
2) Forms
3) Buttons/Actions
4) Images/Assets
5) Texts (including spelling and grammar in the specified language)
6) Accessibility
7) Links
8) Responsiveness


Rules:
- You must ALWAYS include all defects confirmed by TELEMETRY_JSON if any exist.
- Respond in {response_language}.
- TOLERANCE: {tolerance_level}
    When analyzing the visible texts on the site, check if they contain
    spelling or grammar errors according to the requested language (es, en, fr, etc.).
    If you find any, report them under the category "Texts" with:
    incorrect word/fragment
    suggested correction
    severity (low if it's a minor error, medium if it makes the message confusing).
"""
    MAX_RETRIES = 4
    attempt = 0
    while True:
        try:
            parts = [prompt, clean_html]
            for img_path in image_paths:
                try:
                    parts.append(Image.open(img_path))
                except Exception as e:
                    print(f"Could not open image {img_path}: {e}")
            resp = model.generate_content(
                parts,
                generation_config={"response_mime_type": "application/json", "temperature": 0.2}
            )
            data = _coerce_json(resp.text or "{}")
            if isinstance(data, list):
                return {"whatISee": "", "needsModification": bool(data), "modifications": data[:12]}
            if not isinstance(data, dict):
                return {"whatISee": "", "needsModification": False, "modifications": []}
            mods = data.get("modifications") or []
            if not isinstance(mods, list):
                mods = []
            data["modifications"] = mods[:12]
            data["needsModification"] = bool(data["modifications"])
            data.setdefault("whatISee", "")
            return data
        except Exception as e:
            attempt += 1
            msg = str(e).lower()
            if attempt <= MAX_RETRIES and any(k in msg for k in ("429", "rate", "exhausted")):
                time.sleep(2 ** attempt + random.uniform(0.5, 1.5))
                continue
            raise
