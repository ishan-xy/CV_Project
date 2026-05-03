import aiofiles
from pathlib import Path
from fastapi import UploadFile, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import datetime

from services.api.app.models.booking import BookingCreate, BookingResponse
from services.api.app.core.config import get_settings
from services.api.app.core.booking_index import index_add
from services.api.app.core.events import publish_photo_stored

settings = get_settings()


async def save_photo(photo: UploadFile, booking_id: str) -> str:
    guest_dir = Path(settings.UPLOAD_DIR) / booking_id
    guest_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(photo.filename).suffix if photo.filename else ".jpg"
    file_path = guest_dir / f"photo{ext}"

    async with aiofiles.open(file_path, "wb") as f:
        while chunk := await photo.read(1024 * 1024):
            await f.write(chunk)

    return str(file_path)


async def create_booking(
    db: AsyncIOMotorDatabase,
    data: BookingCreate,
    photo: UploadFile,
) -> BookingResponse:
    doc = {
        "name": data.name,
        "phone": data.phone,
        "email": data.email,
        "check_in": data.check_in.isoformat(),
        "check_out": data.check_out.isoformat(),
        "room_type": data.room_type.value,
        "num_guests": data.num_guests,
        "num_rooms": data.num_rooms,
        "amount_paid": data.amount_paid,
        "photo_path": None,
        "assigned_rooms": [],
        "status": "confirmed",
        "created_at": datetime.utcnow().isoformat(),
    }

    result = await db["bookings"].insert_one(doc)
    booking_id = str(result.inserted_id)

    photo_path = await save_photo(photo, booking_id)

    await db["bookings"].update_one(
        {"_id": result.inserted_id},
        {"$set": {"photo_path": photo_path}},
    )

    await index_add(booking_id, data.name)
    await publish_photo_stored(booking_id)

    return BookingResponse(
        id=booking_id,
        name=data.name,
        phone=data.phone,
        email=data.email,
        check_in=data.check_in,
        check_out=data.check_out,
        room_type=data.room_type,
        num_guests=data.num_guests,
        num_rooms=data.num_rooms,
        amount_paid=data.amount_paid,
        photo_path=photo_path,
        assigned_rooms=[],
        status="confirmed",
    )


async def get_booking_by_id(db: AsyncIOMotorDatabase, booking_id: str) -> dict:
    if not ObjectId.is_valid(booking_id):
        raise HTTPException(status_code=400, detail="Invalid booking ID")

    booking = await db["bookings"].find_one({"_id": ObjectId(booking_id)})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    booking["id"] = str(booking["_id"])
    return booking