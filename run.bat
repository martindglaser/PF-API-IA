@echo off
call venv\Scripts\activate
flask --app app/main.py run --port 5001