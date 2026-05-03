from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from datetime import date

from services.api.app.models.booking import CheckInRequest, CheckInResponse, RoomType
from services.api.app.controllers.room_controller import assign_rooms
from services.api.app.utils.security import generate_checkin_token, generate_qr
from services.api.app.utils.email import send_checkin_email

async def process_check_in(
    db: AsyncIOMotorDatabase,
    payload: CheckInRequest,
) -> CheckInResponse:
    if not ObjectId.is_valid(payload.booking_id):
        raise HTTPException(status_code=400, detail="Invalid booking ID")

    booking_oid = ObjectId(payload.booking_id)
    booking = await db["bookings"].find_one({"_id": booking_oid})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking["status"] == "checked_in":
        raise HTTPException(status_code=409, detail="Guest is already checked in")

    if booking["status"] == "cancelled":
        raise HTTPException(status_code=409, detail="Booking is cancelled")

    scheduled_check_in = date.fromisoformat(booking["check_in"])
    if payload.actual_check_in < scheduled_check_in:
        raise HTTPException(
            status_code=400,
            detail=f"Check-in date cannot be before scheduled date: {scheduled_check_in}",
        )

    try:
        assigned_rooms = await assign_rooms(
            db=db,
            room_type=RoomType(booking["room_type"]),
            num_rooms=booking["num_rooms"],
            check_in=booking["check_in"],
            check_out=booking["check_out"],
            exclude_booking_id=booking_oid,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    await db["bookings"].update_one(
        {"_id": booking_oid},
        {
            "$set": {
                "status": "checked_in",
                "actual_check_in": payload.actual_check_in.isoformat(),
                "assigned_rooms": assigned_rooms,
            }
        },
    )

    token_payload = {
        "booking_id": payload.booking_id,
        "name": booking["name"],
        "room_type": booking["room_type"],
        "rooms": assigned_rooms,
        "check_in": booking["check_in"],
        "check_out": booking["check_out"],
    }

    token = generate_checkin_token(token_payload)

    qr_path = generate_qr(token, payload.booking_id)

    send_checkin_email(booking["email"], qr_path)

    return CheckInResponse(
        booking_id=payload.booking_id,
        status="checked_in",
        message=f"Guest {booking['name']} checked in. QR sent via email.",
        assigned_rooms=assigned_rooms,
    )