from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from services.api.app.db.database import get_database
from services.api.app.models.booking import RoomConfigUpdate, RoomConfigResponse
from services.api.app.controllers.room_controller import update_rooms_per_floor, get_hotel_config

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/room-config", response_model=RoomConfigResponse)
async def get_room_config(db: AsyncIOMotorDatabase = Depends(get_database)):
    config = await get_hotel_config(db)
    if not config:
        raise HTTPException(status_code=404, detail="Room config not found")
    return RoomConfigResponse(
        total_floors=config["total_floors"],
        rooms_per_floor=config["rooms_per_floor"],
        room_type_distribution=config["room_type_distribution"],
    )


@router.patch("/room-config", response_model=RoomConfigResponse)
async def update_room_config(
    payload: RoomConfigUpdate,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    updated = await update_rooms_per_floor(db, payload.rooms_per_floor)
    return RoomConfigResponse(
        total_floors=updated["total_floors"],
        rooms_per_floor=updated["rooms_per_floor"],
        room_type_distribution=updated["room_type_distribution"],
    )