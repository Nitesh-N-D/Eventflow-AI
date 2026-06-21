from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import engine
import app.models  # noqa: F401
from app.api.auth import router as auth_router
from app.api.events import router as events_router
from app.api.other_routes import (
    feedback_router, analytics_router, corridors_router
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tables are created via SQL migrations (001_initial_schema.sql).
    # Do NOT call Base.metadata.create_all here — it uses prepared
    # statements internally which breaks with Supabase PgBouncer.
    yield
    await engine.dispose()


app = FastAPI(
    title="EventFlow AI API",
    description=(
        "Event-Driven Traffic Impact Prediction & Smart Traffic Management. "
        "ML models trained on real ASTRAM Bengaluru incident data."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(events_router)
app.include_router(feedback_router)
app.include_router(analytics_router)
app.include_router(corridors_router)


@app.get("/")
def root():
    return {
        "service": "EventFlow AI",
        "status": "ok",
        "ml_data_provenance": "real_astram_bengaluru_dataset",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "ok"}