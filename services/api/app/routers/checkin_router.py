from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from services.api.app.db.database import get_database
from services.api.app.models.booking import CheckInRequest, CheckInResponse
from services.api.app.controllers.checkin_controller import process_check_in

router = APIRouter(prefix="/checkin", tags=["Check-In"])


@router.post("/", response_model=CheckInResponse)
async def check_in_guest(
    payload: CheckInRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await process_check_in(db, payload)