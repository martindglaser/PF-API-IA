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
    """
  
    """
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
    response_language: str = "Spanish",
    categories=None
) -> Dict[str, Any]:
    
    category_definitions = {
        "UI/Styles": "UI/Styles",
        "Forms": "Forms",
        "Links": "Links (Cross-reference with telemetry)",
        "Images/Assets": "Images/Assets",
        "Texts": f"Texts (Check for spelling/grammar errors in {response_language})",
        "Responsiveness": 'Responsiveness (This is mandatory if <image_count> is 2. See <rule id="responsiveness">)'
    }

    if categories:
        normalized = [str(c).strip() for c in categories if str(c).strip()]
        seen = set()
        selected_categories = []
        for c in normalized:
            if c in seen:
                continue
            seen.add(c)
            selected_categories.append(c)
    else:
        # Si no mandan nada desde el request, usamos todas (comportamiento anterior)
        selected_categories = list(category_definitions.keys())

    cat_lines = []
    for idx, key in enumerate(selected_categories, start=1):
        desc = category_definitions.get(key, key)
        cat_lines.append(f"    {idx}. {desc}")
    categories_block = "\n".join(cat_lines) if cat_lines else ""

    prompt = f"""
    <role>
    You are an expert QA (Quality Assurance) analyst specializing in visual UI/UX testing and front-end error detection.
    </role>

    <objective>
    Analyze the provided website screenshots, HTML content, and telemetry data to identify visual, functional, and text errors.
    </objective>

    <input_data>
    <image_count>{len(image_paths)}</image_count>
    <html_content>
    {clean_html}
    </html_content>
    </input_data>

    <critical_rules>
    <rule id="anti-bot">
    FIRST: review <html_content>. If you detect anti-bot measures (captcha, recaptcha, "verify you are human", etc.), you MUST STOP and return ONLY this valid JSON:
    {{"whatISee":"Page blocked by anti-bot: <brief reason in {response_language}>", "needsModification": false, "modifications": []}}
    If not, proceed.
    </rule>

    <rule id="telemetry">
    If <html_content> includes a block, you MUST use it as objective evidence (broken links/images).
    You MUST include these confirmed defects in the "modifications" array.
    </rule>

    <rule id="responsiveness">
    You have been provided with {len(image_paths)} image(s).
    If <image_count> is 2, this is a high-priority task:
    You MUST compare the first image (desktop) and the second image (mobile) to find responsiveness errors.
    - Look for elements that are misaligned, overlapping, or cropped ONLY on mobile.
    - Look for content that doesn't fit the mobile screen (causing horizontal scroll).
    - Report these failures under the "Responsiveness" category.
    </rule>
    </critical_rules>

    <analysis_criteria>
    <tolerance_level name="{tolerance_level}">
    You must adhere to this tolerance level when evaluating visual errors.
    </tolerance_level> 

    <categories_to_check>
{categories_block}
    </categories_to_check>
    </analysis_criteria>

    <output_instructions>
    <format>
    You must return ONLY a valid JSON object.
    </format>
    <language>
    All descriptive strings must be in {response_language}.
    </language>
    <json_structure>
    {{
        "whatISee": "string (A brief description in {response_language} of what the website appears to be).",
        "needsModification": "boolean (true if errors were found)",
        "modifications": [
            {{
                "category": "string" (</categories_to_check>),
                "description": "string (brief, 10–80 characters, in {response_language})",
                "severity": "string (Critical, Medium, Low)",
                "state": "string (confirmed or inconclusive)",
                "selector_css": "string (CSS selector if available, or 'body' if not)",
                "refactoring_suggestion": "string (suggested code or design improvements, maximum 500 characters)"
            }}
        ]
    }}
    </json_structure>
    <final_rule>
    If no defects are found, return:
    {{"whatISee":"<description>", "needsModification": false, "modifications": []}}
    </final_rule>
    </output_instructions>
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