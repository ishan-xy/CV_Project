from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, Literal
from datetime import date
from enum import Enum


class RoomType(str, Enum):
    STANDARD = "Standard"
    DELUXE = "Deluxe"
    SUPER_DELUXE = "Super Deluxe"
    EXECUTIVE = "Executive"
    SUITE = "Suite"


ROOM_TYPE_MAX_ROOMS: dict[RoomType, int] = {
    RoomType.STANDARD: 5,
    RoomType.DELUXE: 4,
    RoomType.SUPER_DELUXE: 3,
    RoomType.EXECUTIVE: 2,
    RoomType.SUITE: 1,
}


class BookingBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., pattern=r"^\+?[1-9]\d{6,14}$")
    email: EmailStr
    check_in: date
    check_out: date
    room_type: RoomType
    num_guests: int = Field(..., ge=1, le=20)
    num_rooms: int = Field(..., ge=1)
    amount_paid: float = Field(..., ge=0)

    @field_validator("check_out")
    @classmethod
    def check_out_after_check_in(cls, v, info):
        if "check_in" in info.data and v <= info.data["check_in"]:
            raise ValueError("check_out must be after check_in")
        return v

    @field_validator("num_rooms")
    @classmethod
    def validate_num_rooms_for_type(cls, v, info):
        if "room_type" in info.data:
            max_allowed = ROOM_TYPE_MAX_ROOMS.get(info.data["room_type"], 5)
            if v > max_allowed:
                raise ValueError(
                    f"Maximum {max_allowed} rooms allowed for {info.data['room_type']}"
                )
        return v


class BookingCreate(BookingBase):
    pass


class BookingResponse(BookingBase):
    id: str
    photo_path: Optional[str] = None
    assigned_rooms: list[str] = []
    status: str = "confirmed"

    class Config:
        from_attributes = True


class BookingInDB(BookingBase):
    photo_path: Optional[str] = None
    assigned_rooms: list[str] = []
    status: str = "confirmed"


class RoomConfigUpdate(BaseModel):
    rooms_per_floor: int = Field(..., ge=10, le=200)


class RoomConfigResponse(BaseModel):
    total_floors: int
    rooms_per_floor: int
    room_type_distribution: dict[str, int]


class CheckInRequest(BaseModel):
    booking_id: str
    actual_check_in: date


class CheckInResponse(BaseModel):
    booking_id: str
    status: str
    message: str
    assigned_rooms: list[str]


class CheckOutRequest(BaseModel):
    booking_id: str
    actual_check_out: date


class CheckOutResponse(BaseModel):
    booking_id: str
    status: str
    message: str