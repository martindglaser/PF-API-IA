# Playwright + Python con navegadores ya instalados
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

WORKDIR /app

# Evita archivos .pyc y fuerza logs en consola
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código de la API
COPY . .

# Flask en 0.0.0.0:5001 (según tu README)
EXPOSE 5001
ENV FLASK_APP=app/main.py
CMD ["flask", "run", "--host", "0.0.0.0", "--port", "5001"]
