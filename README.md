1. python -m venv venv
2. source venv/bin/activate  # En Windows: venv\Scripts\activate
3. pip install -r requirements.txt
4. playwright install chromium # Instala el navegador que usa Playwright
5. flask --app app/main.py run --port 5001


Endpoints
    - POST: /analyze
        Params
            url,
            tolerance (high, medium or low), --> Optional
            language (es, en, de, fr, it, pt) --> optional
        Response
            whatISee: String,
            needsModification: Boolean,
            modifications: String[]
### 1. `/analyze`
Analiza una URL, captura HTML + screenshot, y devuelve un JSON con defectos detectados (IA + telemetría).

**Request:**
```json
POST http://127.0.0.1:5001/analyze
{
  "url": "https://practice-automation.com/broken-links/",
  "tolerance": "medium",
  "language": "es"
}
