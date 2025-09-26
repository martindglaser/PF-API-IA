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
    candidate = s[start:end + 1].strip()
    try:
        return json.loads(candidate)
    except Exception:
        return {"whatISee": "", "needsModification": False, "modifications": []}

def analyze_content(
    clean_html: str,
    image_path: str,
    tolerance_level: str,
    response_language: str = "Spanish"
) -> Dict[str, Any]:
    prompt = f"""
You are a Front-End QA error detector. FIND DEFECTS first.
Return ONLY valid JSON. If no defects: return {{"whatISee":"", "needsModification": false, "modifications":[]}}.
If the HTML includes a comment block <!-- TELEMETRY_JSON ... TELEMETRY_JSON_END -->, use that telemetry as objective evidence (e.g., broken links, broken images) and report them with the proper categories.

Output (strict):
- JSON object with keys: "whatISee":string, "needsModification":boolean, "modifications":array (max 12).
- Each item in "modifications" must be:
{{
  "id": "H-###",
  "categoria": "UI/Estilos|Formularios|Botones|Imagenes|Textos|Accesibilidad|Enlaces|Responsividad",
  "severidad": "Critico|Medio|Bajo",
  "descripcion": "Defecto observable y objetivo.",
  "pasos_repro": ["Paso 1...", "Paso 2..."],
  "selector_css": "CSS/XPath si identificable",
  "evidencia": {{
    "viewport": "desconocido",
    "screenshot_ref": "screenshot_base",
    "dom_snippet": "<...>"
  }},
  "resultado_esperado": "Comportamiento correcto.",
  "resultado_obtenido": "Qué ocurre ahora.",
  "wcag": [],
  "estado": "confirmado|inconcluso"
}}

Severity:
- Critico: bloqueo, 4xx/5xx, pérdida de datos, solapamiento que impide click, no usable en mobile/desktop.
- Medio: validaciones, foco, mensajes, contraste límite, redirecciones incorrectas.
- Bajo: inconsistencias visuales menores.

Mandatory categories to check:
1) UI/Estilos (desalineados/superposiciones/overflow)
2) Formularios (obligatorios/formatos/mensajes/focus)
3) Botones/Acciones (feedback/disabled/eventos duplicados)
4) Imagenes/Recursos (rotas naturalWidth=0, sin alt, sin lazy-loading)
5) Textos (lista vacía sin “no hay datos”, truncado)
6) Accesibilidad (labels, tab, foco, roles/aria, contraste < 4.5:1)
7) Enlaces (404/5xx, anchors vacíos, javascript:void(0))
8) Responsividad (si se observa en HTML; si no, marcar inconcluso)

Rules:
- Prioriza defectos confirmados por la TELEMETRY_JSON si existe.
- No describas la página si hay defectos: lista los defectos primero.
- Si no puedes confirmar algo por falta de datos, usa "estado":"inconcluso".
- Responde en {response_language}.
- TOLERANCE: {tolerance_level}

--- BEGIN HTML (clean + optional telemetry) ---
{clean_html}
--- END HTML ---
"""
    MAX_RETRIES = 4
    attempt = 0
    while True:
        try:
            parts = [prompt, Image.open(image_path)]
            resp = model.generate_content(
                parts,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0.2
                }
            )
            data = _coerce_json(resp.text or "{}")
            if isinstance(data, list):
                needs = len(data) > 0
                return {"whatISee": "", "needsModification": needs, "modifications": data[:12]}
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
            if attempt <= MAX_RETRIES and any(x in str(e).lower() for x in ["429", "rate", "exhausted"]):
                time.sleep(2 ** attempt + random.uniform(0.5, 1.5))
                continue
            raise
