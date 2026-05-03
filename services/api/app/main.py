from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager
from pathlib import Path

from services.api.app.db.database import connect_db, disconnect_db
from services.api.app.routers import checkout_router
from services.api.app.core.config import get_settings
from services.api.app.core.events import init_publisher, close_publisher
from services.api.app.routers import admin_router, booking_router, checkin_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    init_publisher()
    await connect_db()
    yield
    await disconnect_db()
    close_publisher()


app = FastAPI(
    title="Hotel Booking API",
    version="1.0.0",
    description="Production-grade hotel booking backend with MongoDB",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

app.include_router(booking_router.router)
app.include_router(admin_router.router)
app.include_router(checkin_router.router)
app.include_router(checkout_router.router)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "service": "Hotel Booking API"}