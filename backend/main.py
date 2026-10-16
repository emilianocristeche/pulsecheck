from pathlib import Path

from dotenv import load_dotenv

# Load .env before importing modules that read env vars at import time
# (database.py, alerts.py): backend/.env first, then the repo-root .env.
# Neither overrides variables already set in the real environment.
_BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(_BACKEND_DIR / ".env")
load_dotenv(_BACKEND_DIR.parent / ".env")

import os  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from database import init_db  # noqa: E402
from scheduler import start_scheduler, stop_scheduler  # noqa: E402
from routers import endpoints, checks  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="PulseCheck", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    # Comma-separated list, e.g. CORS_ORIGINS=https://your-dashboard.vercel.app
    allow_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(endpoints.router, prefix="/api/endpoints", tags=["endpoints"])
app.include_router(checks.router, prefix="/api/checks", tags=["checks"])


@app.get("/health")
def health():
    return {"status": "ok"}
