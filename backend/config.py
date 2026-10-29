"""Local addresses for the FastAPI development server."""

from pathlib import Path

from dotenv import dotenv_values


VALUES = dotenv_values(Path(__file__).resolve().parent / ".env.local")
HOST = VALUES.get("BACKEND_HOST") or "127.0.0.1"
PORT = int(VALUES.get("BACKEND_PORT") or "8000")
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in (VALUES.get("FRONTEND_ORIGINS") or "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]
SESSION_COOKIE_SECURE = (VALUES.get("SESSION_COOKIE_SECURE") or "false").lower() == "true"
SMTP_HOST = VALUES.get("SMTP_HOST") or ""
SMTP_PORT = int(VALUES.get("SMTP_PORT") or "465")
SMTP_USERNAME = VALUES.get("SMTP_USERNAME") or ""
SMTP_PASSWORD = VALUES.get("SMTP_PASSWORD") or ""
SMTP_FROM = VALUES.get("SMTP_FROM") or SMTP_USERNAME
SMTP_SECURITY = (VALUES.get("SMTP_SECURITY") or "ssl").lower()
