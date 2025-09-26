# app/services/analyze_service.py
import os
import re
import json
import time
import random
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from PIL import Image
import google.generativeai as genai



load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

MODEL_ID = os.getenv("GEMINI_MODEL_ID", "gemini-2.5-flash-lite")
model = genai.GenerativeModel(MODEL_ID)

def is_429(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "429" in msg or "rate" in msg or "resource has been exhausted" in msg

def extract_retry_delay(exc: Exception, default_secs: int = 30) -> int:

    return default_secs

def _coerce_json(txt: str) -> Any:
    """
    Extrae y parsea el primer bloque JSON válido de la respuesta del modelo.
    Soporta code fences ```json ... ```, texto extra antes/después,
    y respuestas que devuelven objeto {} o array [].
    """
    s = (txt or "").strip()


    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s)
    s = re.sub(r"```(?:json)?", "", s, flags=re.IGNORECASE).replace("```", "")


    starts = [i for i in (s.find("{"), s.find("[")) if i != -1]
    if not starts:
        raise ValueError("No se encontró inicio de JSON en la respuesta del modelo.")
    start = min(starts)

   
    end_brace = s.rfind("}")
    end_bracket = s.rfind("]")
    end = max(end_brace, end_bracket)
    if end == -1 or end < start:
        raise ValueError("No se encontró fin de JSON en la respuesta del modelo.")

    candidate = s[start:end + 1].strip()
    return json.loads(candidate)


def analyze_content(
    clean_html: str,
    image_path: str,
    tolerance_level: str,
    response_language: str = "Spanish",
    telemetry_json: Optional[Dict[str, Any]] = None,
    viewports: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Devuelve SOLO JSON con hallazgos priorizando DEFECTOS.
    Si no hay defectos:
      { "whatISee": "", "needsModification": false, "modifications": [] }
    """
    telemetry_json = telemetry_json or {}
    viewports = viewports or []

    prompt = f"""
You are a Front-End QA error detector. FIND DEFECTS first.
Return ONLY valid JSON. If no defects: return {{"whatISee":"", "needsModification": false, "modifications":[]}}.

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
    "viewport": "mobile|tablet|desktop",
    "screenshot_ref": "nombre del screenshot si aplica",
    "dom_snippet": "<...>",
    "telemetria": []
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
8) Responsividad (scroll horizontal, layout roto en {viewports})

Use the TELEMETRY first to confirm defects; screenshots/HTML to exemplify.
If you cannot confirm a suspected issue, mark "estado": "inconcluso" and say what is missing.
Write your response in {response_language}.
TOLERANCE: {tolerance_level}

--- BEGIN TELEMETRY JSON ---
{json.dumps(telemetry_json, ensure_ascii=False)}
--- END TELEMETRY JSON ---

--- BEGIN HTML (clean) ---
{clean_html}
--- END HTML ---
"""

    MAX_RETRIES = 5
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

            data.setdefault("whatISee", "")
            mods = data.get("modifications") or []
            if not isinstance(mods, list):
                mods = []
            if len(mods) > 12:
                mods = mods[:12]
            data["modifications"] = mods
            data["needsModification"] = bool(mods)

            return data

        except Exception as e:
            attempt += 1
            if is_429(e) and attempt <= MAX_RETRIES:
                delay = max(extract_retry_delay(e, 30), 2 ** attempt) + random.uniform(0.5, 1.5)
                time.sleep(delay)
                continue
           
            raise
