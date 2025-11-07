
FROM mcr.microsoft.com/playwright/python:v1.55.0-jammy

WORKDIR /app


ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .


EXPOSE 5001
ENV FLASK_APP=app/main.py
CMD ["flask", "run", "--host", "0.0.0.0", "--port", "5001"]
