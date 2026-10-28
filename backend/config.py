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
