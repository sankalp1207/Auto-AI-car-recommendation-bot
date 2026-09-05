import logging
from fastapi import FastAPI, APIRouter, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.database.database import engine, Base
from app.config import CORS_ORIGINS

# Models
from app.models.car import Car
from app.models.user import User
from app.models.wishlist import Wishlist

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

print("[AutoAI] Database configured successfully.")
print("[AutoAI] Initializing database tables...")
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AutoAI",
    version="1.0.0"
)

@app.on_event("startup")
def startup_event():
    print("[AutoAI] Starting application services...")
    try:
        from app.services.car_data_service import car_data_service
        car_data_service.load_dataset()
        print("[AutoAI] Vehicle inventory loaded successfully!")
    except Exception as e:
        logging.error(f"[AutoAI] Error during startup dataset loading: {e}", exc_info=True)


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
