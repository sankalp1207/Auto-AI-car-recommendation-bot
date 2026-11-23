import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.database.database import engine, Base
from app.config import CORS_ORIGINS

# Models (imported so SQLAlchemy registers them before create_all)
from app.models.car import Car  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.wishlist import Wishlist  # noqa: F401

# Routers
from app.routers.recommendation_router import router as recommendation_router
from app.routers.chat_router import router as chat_router
from app.routers.comparison_router import router as comparison_router
from app.routers.wishlist_router import router as wishlist_router
from app.routers.auth_router import router as auth_router
from app.routers.car_router import router as car_router
from app.routers.dashboard_router import router as dashboard_router
from app.routers.search_router import router as search_router
from app.routers.admin_router import router as admin_router
from app.routers.favorite_router import router as favorite_router
from app.routers.finder_router import router as finder_router
from app.routers.launches_router import router as launches_router
from app.routers.data_quality_router import router as data_quality_router
from app.routers.tco_router import router as tco_router
from app.routers.price_router import router as price_router
from app.routers.garage_router import router as garage_router
from app.routers.alert_router import router as alert_router
from app.routers.feedback_router import router as feedback_router
from app.routers.telemetry_router import router as telemetry_router
from app.services.monitoring_service import monitoring_service
import time


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown logic."""
    print("[AutoAI] Database configured successfully.")
    try:
        print("[AutoAI] Initializing database tables...")
        Base.metadata.create_all(bind=engine)
        print("[AutoAI] Database tables ready.")
    except Exception as e:
        logging.error(f"[AutoAI] DB table initialization failed (non-fatal): {e}")

    try:
        print("[AutoAI] Starting application services...")
        from app.services.car_data_service import car_data_service
        car_data_service.load_dataset()
        print("[AutoAI] Vehicle inventory loaded successfully!")
    except Exception as e:
        logging.error(f"[AutoAI] Error during startup dataset loading: {e}", exc_info=True)

    yield  # Application runs here

    print("[AutoAI] Application shutting down.")


app = FastAPI(
    title="AutoAI",
    version="1.0.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def track_latency_and_metrics(request: Request, call_next):
    start_time = time.time()
    try:
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000.0
        monitoring_service.record_request(duration_ms, is_error=(response.status_code >= 500))
        return response
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000.0
        monitoring_service.record_request(duration_ms, is_error=True)
        raise e

# Regular unversioned routes (for Telegram bot and frontend compatibility)
app.include_router(recommendation_router)
app.include_router(chat_router)
app.include_router(comparison_router)
app.include_router(wishlist_router)
app.include_router(auth_router)
app.include_router(car_router)
app.include_router(dashboard_router)
app.include_router(search_router)
app.include_router(admin_router)
app.include_router(favorite_router)
app.include_router(finder_router)
app.include_router(launches_router)
app.include_router(data_quality_router)
app.include_router(tco_router)
app.include_router(price_router)
app.include_router(garage_router)
app.include_router(alert_router)
app.include_router(feedback_router)
app.include_router(telemetry_router)

# Versioned routes (prefixed with /api/v1 for the Discord bot compatibility)
v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(recommendation_router)
v1_router.include_router(chat_router)
v1_router.include_router(comparison_router)
v1_router.include_router(wishlist_router)
v1_router.include_router(auth_router)
v1_router.include_router(car_router)
v1_router.include_router(dashboard_router)
v1_router.include_router(search_router)
v1_router.include_router(admin_router)
v1_router.include_router(favorite_router)
v1_router.include_router(finder_router)
v1_router.include_router(launches_router)
v1_router.include_router(data_quality_router)
v1_router.include_router(tco_router)
v1_router.include_router(price_router)
v1_router.include_router(garage_router)
v1_router.include_router(alert_router)
v1_router.include_router(feedback_router)
v1_router.include_router(telemetry_router)

app.include_router(v1_router)

@app.get("/health", tags=["Health"])
def health_check(response: Response):
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        logging.error(f"[AutoAI] Health check database connectivity failed: {e}")
        response.status_code = 503
        return {
            "status": "unhealthy",
            "database": "disconnected"
        }

@app.get("/")
def home():
    return {
        "status": "running",
        "project": "AutoAI"
    }

