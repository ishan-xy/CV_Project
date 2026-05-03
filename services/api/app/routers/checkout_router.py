from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from services.api.app.db.database import get_database
from services.api.app.models.booking import CheckOutRequest, CheckOutResponse
from services.api.app.controllers.checkout_controller import process_check_out

router = APIRouter(prefix="/checkout", tags=["Check-Out"])


@router.post("/", response_model=CheckOutResponse)
async def check_out_guest(
    payload: CheckOutRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    return await process_check_out(db, payload)