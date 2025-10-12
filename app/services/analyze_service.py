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
Eres un detector de errores de Front-End.

PRIMERO: revisa el HTML completo que se te proporciona (segundo elemento del input).
Si detectas que la página está BLOQUEANDO el acceso por medidas anti-bot —específicamente señales claras como: "captcha", "recaptcha", "verify you are human", "please complete the security check", "are you human", "cf-chl-bypass", "cloudflare-challenge"— DEBES devolver SOLO este JSON válido y NADA MÁS:

{{"whatISee":"Página bloqueada por anti-bot: <razón breve en {response_language}>", "needsModification": false, "modifications": []}}

La razón debe ser breve (1–6 palabras) y estar en {response_language} (ej.: "captcha presente", "verificación Cloudflare").
Si NO detectas bloqueo por anti-bot, procede con el análisis normal descrito a continuación.

Devuelve SOLO JSON válido. Si no hay defectos, responde: {{ "whatISee":"", "needsModification": false, "modifications": [] }}.
Si el HTML incluye <!-- TELEMETRY_JSON … TELEMETRY_JSON_END --> úsalo como evidencia objetiva (enlaces/imágenes rotas) y prioriza los defectos confirmados en ese bloque: inclúyelos en "modifications" aunque no sean evidentes en las imágenes.

Salida estricta:
- Objeto JSON con: "whatISee": string, "needsModification": boolean, "modifications": array.
- Cada ítem en "modifications" debe tener SOLO:
  - categoria (UI/Estilos, Formularios, Botones, Imagenes, Textos, Accesibilidad, Enlaces, Responsividad)
  - descripcion
  - severidad (Critico, Medio, Bajo)
  - estado (confirmado o inconcluso)
  - selector_css

Criterios:
1) UI/Estilos
2) Formularios
3) Botones/Acciones
4) Imagenes/Recursos
5) Textos (incluyendo ortografía y gramática en el idioma indicado)
6) Accesibilidad
7) Enlaces
8) Responsividad

Reglas:
- Debes incluir SIEMPRE todos los defectos confirmados por TELEMETRY_JSON si existe alguno.
- Responde en {response_language}.
- TOLERANCE: {tolerance_level}
    Cuando analices los textos visibles del sitio, revisa si contienen
    errores de ortografía o gramática según el idioma solicitado (es, en, fr, etc.). 
    Si encuentras alguno, repórtalo en la categoría "Textos" con:
    palabra/fragmento incorrecto
    sugerencia de corrección
    severidad (bajo si es un error leve, medio si confunde el mensaje).
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
