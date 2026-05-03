from motor.motor_asyncio import AsyncIOMotorDatabase
from services.api.app.models.booking import RoomType


FLOOR_BASE = [100, 200, 300, 400, 500, 600, 700, 800]

ROOM_TYPE_ORDER = [
    RoomType.STANDARD,
    RoomType.DELUXE,
    RoomType.SUPER_DELUXE,
    RoomType.EXECUTIVE,
    RoomType.SUITE,
]


async def get_hotel_config(db: AsyncIOMotorDatabase) -> dict:
    config = await db["room_config"].find_one({"_id": "hotel_config"})
    return config


async def get_room_numbers_for_floor(floor_base: int, config: dict) -> dict[str, list[int]]:
    distribution = config["room_type_distribution"]
    rooms_per_floor = config["rooms_per_floor"]

    room_map: dict[str, list[int]] = {}
    current = floor_base + 1

    for room_type in ROOM_TYPE_ORDER:
        count = distribution.get(room_type.value, 0)
        room_map[room_type.value] = list(range(current, current + count))
        current += count

    return room_map


async def assign_rooms(
    db: AsyncIOMotorDatabase,
    room_type: RoomType,
    num_rooms: int,
    check_in: str,
    check_out: str,
    exclude_booking_id=None,
) -> list[str]:
    config = await get_hotel_config(db)
    bookings_col = db["bookings"]

    conflict_query = {
        "room_type": room_type.value,
        "status": {"$in": ["confirmed", "checked_in"]},
        "check_in": {"$lt": check_out},
        "check_out": {"$gt": check_in},
        "assigned_rooms": {"$ne": []},
    }
    if exclude_booking_id is not None:
        conflict_query["_id"] = {"$ne": exclude_booking_id}

    for floor_base in FLOOR_BASE:
        room_map = await get_room_numbers_for_floor(floor_base, config)
        available_rooms = room_map.get(room_type.value, [])

        booked_cursor = bookings_col.find(conflict_query, {"assigned_rooms": 1})

        booked_rooms = set()
        async for booking in booked_cursor:
            for room in booking.get("assigned_rooms", []):
                booked_rooms.add(room)

        free_rooms = [
            str(r) for r in available_rooms if str(r) not in booked_rooms
        ]

        if len(free_rooms) >= num_rooms:
            return free_rooms[:num_rooms]

    raise ValueError(
        f"No available {room_type.value} rooms for the selected dates"
    )


async def update_rooms_per_floor(db: AsyncIOMotorDatabase, rooms_per_floor: int) -> dict:
    standard = int(rooms_per_floor * 0.40)
    deluxe = int(rooms_per_floor * 0.28)
    super_deluxe = int(rooms_per_floor * 0.18)
    executive = int(rooms_per_floor * 0.10)
    suite = rooms_per_floor - standard - deluxe - super_deluxe - executive

    distribution = {
        "Standard": standard,
        "Deluxe": deluxe,
        "Super Deluxe": super_deluxe,
        "Executive": executive,
        "Suite": suite,
    }

    result = await db["room_config"].find_one_and_update(
        {"_id": "hotel_config"},
        {"$set": {"rooms_per_floor": rooms_per_floor, "room_type_distribution": distribution}},
        return_document=True,
    )
    return result