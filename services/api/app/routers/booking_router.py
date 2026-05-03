from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import date
from typing import Annotated

from services.api.app.db.database import get_database
from services.api.app.models.booking import BookingCreate, BookingResponse, RoomType
from services.api.app.controllers.booking_controller import create_booking, get_booking_by_id

router = APIRouter(prefix="/bookings", tags=["Bookings"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@router.post("/", response_model=BookingResponse, status_code=201)
async def create_booking_route(
    name: Annotated[str, Form()],
    phone: Annotated[str, Form()],
    email: Annotated[str, Form()],
    check_in: Annotated[date, Form()],
    check_out: Annotated[date, Form()],
    room_type: Annotated[RoomType, Form()],
    num_guests: Annotated[int, Form()],
    num_rooms: Annotated[int, Form()],
    amount_paid: Annotated[float, Form()],
    photo: Annotated[UploadFile, File()],
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    if photo.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_IMAGE_TYPES)}",
        )

    booking_data = BookingCreate(
        name=name,
        phone=phone,
        email=email,
        check_in=check_in,
        check_out=check_out,
        room_type=room_type,
        num_guests=num_guests,
        num_rooms=num_rooms,
        amount_paid=amount_paid,
    )

    return await create_booking(db, booking_data, photo)


@router.get("/{booking_id}", status_code=200)
async def get_booking_route(
    booking_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await get_booking_by_id(db, booking_id)