from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import init_db
from scheduler import start_scheduler, stop_scheduler
from routers import endpoints, checks


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="PulseCheck", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ponytail: lock to VITE_API_URL in prod via env
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(endpoints.router, prefix="/api/endpoints", tags=["endpoints"])
app.include_router(checks.router, prefix="/api/checks", tags=["checks"])


@app.get("/health")
def health():
    return {"status": "ok"}
