"""Start FastAPI using backend/.env.local."""

import uvicorn

from backend.config import HOST, PORT


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=True)
