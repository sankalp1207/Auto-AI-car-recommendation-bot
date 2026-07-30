import logging
from fastapi import FastAPI, APIRouter, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.database.database import engine, Base

# Models
from app.models.car import Car
from app.models.user import User
from app.models.wishlist import Wishlist
from app.models.erp_session import ERPSession

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
from app.routers.erp_router import router as erp_router, students_router


print("DATABASE:", engine.url)
print("Creating tables...")
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AutoAI",
    version="1.0.0"
)

@app.on_event("startup")
def startup_event():
    print("Startup: Seeding database from CSV...")
    try:
        from app.services.car_data_service import car_data_service
        car_data_service.load_dataset()
        print("Startup: Seeding completed successfully!")
    except Exception as e:
        print(f"Startup: Error seeding database: {e}")

# Setup Logger
logger = logging.getLogger("erp_middleware")

@app.middleware("http")
async def log_erp_requests(request: Request, call_next):
    # Extract headers
    discord_command = request.headers.get("x-discord-command", "N/A")
    discord_user_id = request.headers.get("x-discord-user-id", "N/A")
    method = request.method
    url = str(request.url)
    
    # Process request
    response = await call_next(request)
    
    # Read response body for logging
    response_body = b""
    async for chunk in response.body_iterator:
        response_body += chunk
        
    # Re-create response since we consumed the body iterator
    new_response = Response(
        content=response_body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type
    )
    
    # Try to decode response body to string
    try:
        body_str = response_body.decode("utf-8")
    except Exception:
        body_str = "<binary>"
        
    # Log in the format requested:
    # Incoming Discord command ↓ Backend URL ↓ HTTP Method ↓ Response Status ↓ Response Body
    log_msg = (
        f"\n[REQUEST LOG]\n"
        f"Incoming Discord command: {discord_command}\n"
        f"User ID: {discord_user_id}\n"
        f"Backend URL: {url}\n"
        f"HTTP Method: {method}\n"
        f"Response Status: {response.status_code}\n"
        f"Response Body: {body_str[:1000]}..." if len(body_str) > 1000 else body_str
    )
    print(log_msg)
    logger.info(log_msg)
    
    return new_response

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
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
app.include_router(erp_router)
app.include_router(students_router)

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
v1_router.include_router(erp_router)
v1_router.include_router(students_router)

app.include_router(v1_router)

@app.get("/")
def home():
    return {
        "status": "running",
        "project": "AutoAI"
    }
