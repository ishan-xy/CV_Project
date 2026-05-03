import shutil
from pathlib import Path
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import date

from services.api.app.models.booking import CheckOutRequest, CheckOutResponse
from services.api.app.core.config import get_settings
from services.api.app.core.booking_index import index_remove
from services.api.app.core.events import publish_photo_deleted

settings = get_settings()


async def process_check_out(
    db: AsyncIOMotorDatabase,
    payload: CheckOutRequest,
) -> CheckOutResponse:
    if not ObjectId.is_valid(payload.booking_id):
        raise HTTPException(status_code=400, detail="Invalid booking ID")

    booking_oid = ObjectId(payload.booking_id)
    booking = await db["bookings"].find_one({"_id": booking_oid})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking["status"] == "checked_out":
        raise HTTPException(status_code=409, detail="Guest is already checked out")

    if booking["status"] == "cancelled":
        raise HTTPException(status_code=409, detail="Booking is cancelled")

    if booking["status"] != "checked_in":
        raise HTTPException(status_code=409, detail="Guest has not checked in yet")

    scheduled_check_out = date.fromisoformat(booking["check_out"])
    if payload.actual_check_out < date.fromisoformat(booking["check_in"]):
        raise HTTPException(
            status_code=400,
            detail="Check-out date cannot be before check-in date",
        )

    guest_dir = Path(settings.UPLOAD_DIR) / payload.booking_id
    if guest_dir.exists():
        shutil.rmtree(guest_dir)
        await publish_photo_deleted(payload.booking_id)

    await index_remove(payload.booking_id)

    await db["bookings"].update_one(
        {"_id": booking_oid},
        {
            "$set": {
                "status": "checked_out",
                "actual_check_out": payload.actual_check_out.isoformat(),
                "photo_path": None,
                "assigned_rooms": [],
            }
        },
    )

    return CheckOutResponse(
        booking_id=payload.booking_id,
        status="checked_out",
        message=f"Guest {booking['name']} has been successfully checked out.",
    )