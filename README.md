# 🤖 PF-API-IA
## Servicio de Inteligencia Artificial – Plataforma BDT Global
Microservicio especializado en análisis automatizado de páginas web mediante IA (Google Gemini), captura de screenshots, validación de enlaces e imágenes, y generación de reportes de calidad para equipos de QA.

### 📦 Stack Tecnológico
Este servicio está construido con:

- Python 3.11+
- Flask / Flask-CORS
- Google Generative AI (Gemini 2.5 Flash Lite)
- Playwright 1.55.0
- BeautifulSoup4
- Pillow
- python-dotenv
- cuid

### 🗂️ Estructura del Proyecto
PF-API-IA/
- app/
  - main.py              → Punto de entrada Flask + rutas HTTP
  - services/            → Servicios de análisis, screenshots, validación
  - utils/               → Helpers y limpieza de HTML
- Dockerfile             → Imagen Docker para despliegue
- requirements.txt       → Dependencias Python

## ⚙️ Instalación (Local)

1.  **Clonar el repositorio:**
    Abre tu terminal y clona este repositorio.

    ```bash
    git clone https://github.com/martindglaser/PF-API-IA.git
    ```

2.  **Acceder al directorio:**
    ```bash
    cd PF-API-IA
    ```

3. **Crear entorno virtual**

    ```bash
    python -m venv venv
    ```

4.  **Activar entorno virtual**
    ```bash
    # Windows:
    venv\Scripts\activate
    
    # Linux/Mac:
    source venv/bin/activate
    ```
    
5.  **Instalar dependencias**
    ```bash
    pip install -r requirements.txt
    ```

6.  **Instalar navegador Chromium (Playwright)**
    ```bash
    playwright install chromium
    ```

7.  **Ejecutar el servidor**
    ```bash
    flask --app app/main.py run --port 5001
    ```
    
## 🌐 Endpoints Principales
Una vez corriendo, accedés acá:

| Tipo           | URL                                                            |
| -------------- | -------------------------------------------------------------- |
| **API Base**   | [http://localhost:5001](http://localhost:5001)                 |
| **Health**     | [http://localhost:5001/health](http://localhost:5001/health)   |
